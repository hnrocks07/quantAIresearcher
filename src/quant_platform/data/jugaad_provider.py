"""Jugaad-data NSE provider — F&O bhav copy + equity historical via jugaad_data."""

from __future__ import annotations

import asyncio
import csv
import io
import os
import tempfile
from datetime import date, datetime, timedelta
from typing import Any

from ..plugins.data_provider import DataProvider
from ..logging import get_logger

logger = get_logger("jugaad_provider")

RATE_LIMIT_DELAY = 0.3


def _is_jugaad_available() -> bool:
    try:
        import jugaad_data  # noqa: F401
        return True
    except ImportError:
        return False


class JugaadNSEProvider(DataProvider):

    def __init__(self):
        self._instruments_cache: list[dict[str, Any]] | None = None

    def name(self) -> str:
        return "jugaad_nse"

    async def connect(self) -> None:
        if not _is_jugaad_available():
            logger.warning(
                "jugaad-data package not installed. "
                "Install with: pip install jugaad-data"
            )

    async def disconnect(self) -> None:
        self._instruments_cache = None

    # ------------------------------------------------------------------
    # OHLCV
    # ------------------------------------------------------------------

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date | datetime,
        end_date: date | datetime,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        start_d = start_date.date() if isinstance(start_date, datetime) else start_date
        end_d = end_date.date() if isinstance(end_date, datetime) else end_date
        clean_symbol = symbol.replace(".NS", "").upper()

        # Detect F&O symbols (contain expiry/strike info or explicitly requested)
        if _is_fno_symbol(clean_symbol):
            return await self._fetch_fno_ohlcv(clean_symbol, start_d, end_d)
        return await self._fetch_equity_ohlcv(clean_symbol, start_d, end_d)

    async def _fetch_equity_ohlcv(
        self, symbol: str, start_d: date, end_d: date
    ) -> list[dict[str, Any]]:
        if not _is_jugaad_available():
            logger.warning("jugaad-data not installed, cannot fetch equity OHLCV")
            return []

        loop = asyncio.get_event_loop()

        def _download():
            from jugaad_data.nse import stock_df
            df = stock_df(
                symbol=symbol,
                from_date=start_d,
                to_date=end_d,
                series="EQ",
            )
            return df

        try:
            df = await loop.run_in_executor(None, _download)
            if df is None or df.empty:
                return []

            result = []
            for idx, row in df.iterrows():
                row_date = None
                if hasattr(row, "get"):
                    row_date = row.get("DATE", None)
                if row_date is None:
                    row_date = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
                _get = row.get if hasattr(row, "get") else lambda k, d=0: row.get(k, d) if hasattr(row, "get") else d
                result.append({
                    "date": row_date,
                    "open": float(_get("OPEN", _get("open", 0))),
                    "high": float(_get("HIGH", _get("high", 0))),
                    "low": float(_get("LOW", _get("low", 0))),
                    "close": float(_get("CLOSE", _get("close", 0))),
                    "volume": float(_get("VOLUME", _get("volume", _get("TOTTRDQTY", 0)))),
                })
            return result
        except Exception as e:
            logger.warning(f"Error fetching equity OHLCV for {symbol}: {e}")
            return []

    async def _fetch_fno_ohlcv(
        self, symbol: str, start_d: date, end_d: date
    ) -> list[dict[str, Any]]:
        if not _is_jugaad_available():
            logger.warning("jugaad-data not installed, cannot fetch F&O OHLCV")
            return []

        # Strip F&O keywords to get the base symbol for CSV filtering
        symbol = _strip_fno_keywords(symbol)
        result: list[dict[str, Any]] = []
        current = start_d

        while current <= end_d:
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue

            try:
                rows = await self._fetch_fno_bhav_for_date(current, symbol)
                result.extend(rows)
            except Exception as e:
                logger.debug(f"No F&O bhav data for {current}: {e}")

            current += timedelta(days=1)
            await asyncio.sleep(RATE_LIMIT_DELAY)

        return result

    async def _fetch_fno_bhav_for_date(
        self, dt: date, symbol: str
    ) -> list[dict[str, Any]]:
        loop = asyncio.get_event_loop()

        def _download_and_parse():
            from jugaad_data.nse import bhavcopy_fo_save

            with tempfile.TemporaryDirectory() as tmpdir:
                bhavcopy_fo_save(dt, tmpdir)
                csv_files = [
                    f for f in os.listdir(tmpdir)
                    if f.lower().endswith(".csv")
                ]
                if not csv_files:
                    return []

                rows = []
                csv_path = os.path.join(tmpdir, csv_files[0])
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        row_symbol = row.get("SYMBOL", "").strip()
                        if row_symbol == symbol:
                            rows.append(_parse_fno_row(row, dt))
                return rows

        return await loop.run_in_executor(None, _download_and_parse)

    # ------------------------------------------------------------------
    # Instruments
    # ------------------------------------------------------------------

    async def fetch_instruments(
        self, exchange: str | None = None
    ) -> list[dict[str, Any]]:
        if not _is_jugaad_available():
            logger.warning("jugaad-data not installed, cannot fetch instruments")
            return []

        if exchange and exchange.upper() in ("NSE_FNO", "NFO"):
            return await self._fetch_fno_instruments()

        if exchange and exchange.upper() == "NSE_EQUITY":
            return []

        # Default: return F&O instruments (primary purpose of this provider)
        return await self._fetch_fno_instruments()

    async def _fetch_fno_instruments(self) -> list[dict[str, Any]]:
        if self._instruments_cache is not None:
            return self._instruments_cache

        loop = asyncio.get_event_loop()

        def _download():
            from jugaad_data.nse import bhavcopy_fo_save

            # Try today, then go back up to 5 days to find last trading day
            target = date.today()
            for _ in range(6):
                if target.weekday() >= 5:
                    target -= timedelta(days=1)
                    continue
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        bhavcopy_fo_save(target, tmpdir)
                        csv_files = [
                            f for f in os.listdir(tmpdir)
                            if f.lower().endswith(".csv")
                        ]
                        if not csv_files:
                            target -= timedelta(days=1)
                            continue

                        csv_path = os.path.join(tmpdir, csv_files[0])
                        return _parse_instruments_from_csv(csv_path)
                except Exception:
                    target -= timedelta(days=1)
                    continue
            return []

        try:
            instruments = await loop.run_in_executor(None, _download)
            self._instruments_cache = instruments
            return instruments
        except Exception as e:
            logger.warning(f"Could not fetch F&O instruments: {e}")
            return []

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_symbol(self, query: str) -> list[dict[str, Any]]:
        instruments = await self.fetch_instruments()
        query_upper = query.upper().replace(".NS", "")
        return [
            inst for inst in instruments
            if query_upper in inst["symbol"].upper()
            or query_upper in inst.get("name", "").upper()
        ]


# ======================================================================
# Module-level helpers
# ======================================================================

def _strip_fno_keywords(symbol: str) -> str:
    """Remove F&O keywords (FUT, OPT, CE, PE) from symbol to get the base name."""
    import re
    upper = symbol.upper().strip()
    # Remove common suffixes/words
    for kw in ("FUTURES", "FUTURE", "FUT", "OPTIONS", "OPTION", "OPT"):
        upper = upper.replace(kw, "")
    # Remove standalone CE/PE
    upper = re.sub(r'\bCE\b', '', upper)
    upper = re.sub(r'\bPE\b', '', upper)
    return upper.strip()


def _is_fno_symbol(symbol: str) -> bool:
    """Heuristic: F&O symbols contain keywords like FUT/OPT or CE/PE as separate words."""
    import re
    upper = symbol.upper()
    # Match FUT/OPT anywhere, but CE/PE only as whole words to avoid
    # false positives like "RELIANCE" containing "CE"
    if "FUT" in upper or "OPT" in upper:
        return True
    # Check CE/PE as word boundaries
    if re.search(r'\bCE\b', upper) or re.search(r'\bPE\b', upper):
        return True
    return False


def _parse_fno_row(row: dict, dt: date) -> dict[str, Any]:
    """Parse a single F&O bhav copy CSV row into our standard dict."""
    expiry_str = row.get("EXPIRY_DT", "").strip()
    expiry_date = None
    if expiry_str:
        try:
            expiry_date = datetime.strptime(expiry_str, "%d-%b-%Y").date()
        except ValueError:
            try:
                expiry_date = datetime.strptime(expiry_str, "%d-%B-%Y").date()
            except ValueError:
                pass

    return {
        "date": dt,
        "open": _safe_float(row.get("OPEN")),
        "high": _safe_float(row.get("HIGH")),
        "low": _safe_float(row.get("LOW")),
        "close": _safe_float(row.get("CLOSE")),
        "volume": _safe_float(row.get("CONTRACTS")),
        "open_interest": _safe_float(row.get("OPEN_INT")),
        "settle_price": _safe_float(row.get("SETTLE_PR")),
        "contracts": _safe_float(row.get("CONTRACTS")),
        "val_in_lakh": _safe_float(row.get("VAL_INLAKH")),
        "change_in_oi": _safe_float(row.get("CHG_IN_OI")),
        "instrument": row.get("INSTRUMENT", "").strip(),
        "symbol": row.get("SYMBOL", "").strip(),
        "expiry_date": expiry_date,
        "strike_price": _safe_float(row.get("STRIKE_PR")),
        "option_type": row.get("OPTION_TYP", "").strip(),
    }


def _parse_instruments_from_csv(csv_path: str) -> list[dict[str, Any]]:
    """Extract unique instrument definitions from F&O bhav copy CSV."""
    seen: set[tuple] = set()
    instruments: list[dict[str, Any]] = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row.get("SYMBOL", "").strip()
            instrument = row.get("INSTRUMENT", "").strip()
            expiry_str = row.get("EXPIRY_DT", "").strip()
            strike_str = row.get("STRIKE_PR", "").strip()
            option_typ = row.get("OPTION_TYP", "").strip()

            if not symbol or not instrument:
                continue

            key = (symbol, instrument, expiry_str, strike_str, option_typ)
            if key in seen:
                continue
            seen.add(key)

            # Determine asset_type from INSTRUMENT column
            asset_type = _instrument_to_asset_type(instrument)
            contract_type = instrument

            # Parse expiry date
            expiry_date = None
            if expiry_str:
                try:
                    expiry_date = datetime.strptime(expiry_str, "%d-%b-%Y").date()
                except ValueError:
                    try:
                        expiry_date = datetime.strptime(expiry_str, "%d-%B-%Y").date()
                    except ValueError:
                        pass

            entry: dict[str, Any] = {
                "symbol": symbol,
                "name": symbol,
                "asset_type": asset_type,
                "exchange": "NSE",
                "currency": "INR",
                "contract_type": contract_type,
            }

            if expiry_date:
                entry["expiry_date"] = expiry_date
            if strike_str:
                entry["strike_price"] = _safe_float(strike_str)
            if option_typ:
                entry["option_type"] = option_typ

            instruments.append(entry)

    return instruments


def _instrument_to_asset_type(instrument: str) -> str:
    """Map NSE INSTRUMENT column to our asset_type."""
    upper = instrument.upper()
    if upper in ("FUTIDX", "FUTSTK"):
        return "futures"
    if upper in ("OPTIDX", "OPTSTK"):
        return "options"
    return "futures"


def _safe_float(val: Any) -> float:
    """Convert to float, return 0.0 on failure."""
    if val is None:
        return 0.0
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return 0.0
