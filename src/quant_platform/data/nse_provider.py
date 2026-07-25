"""NSE bhav copy data provider — fetches equity and F&O data from NSE archives."""

from __future__ import annotations

import asyncio
import csv
import io
import zipfile
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from ..plugins.data_provider import DataProvider
from ..logging import get_logger

logger = get_logger("nse_provider")

NSE_EQUITY_BHAV_URL = (
    "https://archives.nseindia.com/content/historical/EQUITIES/{year}/{mon}/cm{ddmonyyyy}bhav.csv.zip"
)
NSE_FO_BHAV_URL = (
    "https://archives.nseindia.com/content/historical/DERIVATIVES/{year}/{mon}/fo{ddmonyyyy}bhav.csv.zip"
)
NSE_NIFTY500_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
NSE_FO_MKTLOTS_URL = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"

RATE_LIMIT_DELAY = 0.5


class NSEProvider(DataProvider):

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    def name(self) -> str:
        return "nse_bhav"

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://www.nseindia.com/",
            },
            timeout=30.0,
            follow_redirects=True,
        )

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("NSEProvider not connected. Call connect() first.")
        return self._client

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date | datetime,
        end_date: date | datetime,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        client = self._ensure_client()

        start_d = start_date.date() if isinstance(start_date, datetime) else start_date
        end_d = end_date.date() if isinstance(end_date, datetime) else end_date

        clean_symbol = symbol.replace(".NS", "").upper()
        result: list[dict[str, Any]] = []
        current = start_d

        while current <= end_d:
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue

            try:
                rows = await self._fetch_bhav_for_date(client, current, clean_symbol)
                result.extend(rows)
            except Exception as e:
                logger.debug(f"No bhav data for {current}: {e}")

            current += timedelta(days=1)
            await asyncio.sleep(RATE_LIMIT_DELAY)

        return result

    async def _fetch_bhav_for_date(
        self, client: httpx.AsyncClient, dt: date, symbol: str
    ) -> list[dict[str, Any]]:
        mon = dt.strftime("%b").upper()
        year = str(dt.year)
        ddmonyyyy = dt.strftime("%d%b%Y").upper()

        url = NSE_EQUITY_BHAV_URL.format(year=year, mon=mon, ddmonyyyy=ddmonyyyy)
        resp = await client.get(url)
        resp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_name = zf.namelist()[0]
            with zf.open(csv_name) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                rows = []
                for row in reader:
                    row_symbol = row.get("SYMBOL", "").strip()
                    if row_symbol == symbol:
                        rows.append({
                            "date": datetime.strptime(row.get("TIMESTAMP", "").strip(), "%d-%b-%Y"),
                            "open": float(row.get("OPEN", 0)),
                            "high": float(row.get("HIGH", 0)),
                            "low": float(row.get("LOW", 0)),
                            "close": float(row.get("CLOSE", 0)),
                            "volume": float(row.get("TOTTRDQTY", 0)),
                        })
                return rows

    async def fetch_instruments(
        self, exchange: str | None = None
    ) -> list[dict[str, Any]]:
        client = self._ensure_client()

        result: list[dict[str, Any]] = []

        if exchange is None or exchange.upper() in ("NSE", "NSE_EQUITY"):
            equity = await self._fetch_equity_instruments(client)
            result.extend(equity)

        if exchange is None or exchange.upper() in ("NSE", "NSE_FNO", "NFO"):
            fno = await self._fetch_fno_instruments(client)
            result.extend(fno)

        return result

    async def _fetch_equity_instruments(
        self, client: httpx.AsyncClient
    ) -> list[dict[str, Any]]:
        try:
            resp = await client.get(NSE_NIFTY500_URL)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            result = []
            for row in reader:
                symbol = row.get("Symbol", "").strip()
                name = row.get("Company Name", symbol).strip()
                if symbol:
                    entry: dict[str, Any] = {
                        "symbol": symbol,
                        "name": name,
                        "asset_type": "equity",
                        "exchange": "NSE",
                        "currency": "INR",
                    }
                    industry = row.get("Industry", "").strip()
                    if industry:
                        entry["sector"] = industry
                    result.append(entry)
            await asyncio.sleep(RATE_LIMIT_DELAY)
            return result
        except Exception as e:
            logger.warning(f"Could not fetch NIFTY 500 instrument list: {e}")
            return []

    async def _fetch_fno_instruments(
        self, client: httpx.AsyncClient
    ) -> list[dict[str, Any]]:
        try:
            resp = await client.get(NSE_FO_MKTLOTS_URL)
            resp.raise_for_status()
            lines = resp.text.strip().split("\n")
            if len(lines) < 2:
                return []

            header = [h.strip() for h in lines[0].split(",")]
            result = []
            for line in lines[1:]:
                cols = [c.strip() for c in line.split(",")]
                if len(cols) < 2:
                    continue
                symbol = cols[0].strip() if cols else ""
                if not symbol or symbol == "":
                    continue

                expiry_cols = header[1:]
                for i, exp_label in enumerate(expiry_cols):
                    col_idx = i + 1
                    if col_idx < len(cols):
                        lot_str = cols[col_idx].strip()
                        if lot_str and lot_str.isdigit() and int(lot_str) > 0:
                            result.append({
                                "symbol": symbol,
                                "name": f"{symbol} Futures",
                                "asset_type": "futures",
                                "exchange": "NSE",
                                "currency": "INR",
                                "contract_type": "futures",
                                "lot_size": int(lot_str),
                                "expiry_label": exp_label.strip(),
                            })
                            break

            await asyncio.sleep(RATE_LIMIT_DELAY)
            return result
        except Exception as e:
            logger.warning(f"Could not fetch F&O lot sizes: {e}")
            return []

    async def search_symbol(self, query: str) -> list[dict[str, Any]]:
        instruments = await self.fetch_instruments(exchange="NSE")
        query_upper = query.upper().replace(".NS", "")
        return [
            inst for inst in instruments
            if query_upper in inst["symbol"].upper() or query_upper in inst.get("name", "").upper()
        ]
