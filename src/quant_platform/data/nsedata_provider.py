"""NSE-Data CSV provider — bulk historical intraday data from pre-downloaded CSV files."""

from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ..plugins.data_provider import DataProvider
from ..logging import get_logger

logger = get_logger("nsedata_provider")

NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "SBIN",
    "BHARTIARTL", "KOTAKBANK", "ITC", "LT", "AXISBANK", "BAJFINANCE", "MARUTI",
    "WIPRO", "SUNPHARMA", "TITAN", "ULTRACEMCO", "NESTLEIND", "TATAMOTORS",
    "POWERGRID", "ONGC", "NTPC", "ADANIENT", "ADANIPORTS", "BAJAJFINSV",
    "HCLTECH", "TATASTEEL", "COALINDIA", "TECHM", "DRREDDY", "BPCL", "DIVISLAB",
    "HEROMOTOCO", "CIPLA", "GRASIM", "EICHERMOT", "APOLLOHOSP", "TATACONSUM",
    "HINDALCO", "JSWSTEEL", "UPL", "SBILIFE", "BRITANNIA", "INDUSINDBK",
    "ASIANPAINT", "M&M", "HDFCLIFE", "BAJAJ-AUTO", "DABUR",
]

NIFTY_NEXT_50 = [
    "ACC", "AMBUJACEM", "BANDHANBNK", "BERGEPAINT", "BIOCON", "COLPAL",
    "CONCOR", "DLF", "GAIL", "GODREJCP", "HAVELLS", "ICICIGI", "ICICIPRULI",
    "INDUSTOWER", "JUBLFOOD", "LUPIN", "MARICO", "MCDOWELL-N", "MUTHOOTFIN",
    "NAUKRI", "PGHH", "PIDILITIND", "PNB", "SBICARD", "SIEMENS",
    "SRF", "TORNTPHARM", "TRENT", "VEDL", "ZOMATO",
]

INTERVAL_FOLDER_MAP = {
    "1m": "1 Minute",
    "3m": "3 Minutes",
    "5m": "5 Minutes",
    "10m": "10 Minutes",
    "15m": "15 Minutes",
    "30m": "30 Minutes",
    "1h": "60 Minutes",
    "1d": "Daily",
}


class NSEDataProvider(DataProvider):

    def __init__(self, data_dir: str | None = None):
        self._data_dir: Path | None = None
        self._custom_dir = data_dir

    def name(self) -> str:
        return "nsedata"

    async def connect(self) -> None:
        if self._custom_dir:
            self._data_dir = Path(self._custom_dir)
        else:
            from ..config import get_settings
            self._data_dir = Path(get_settings().data_dir) / "nsedata"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        csv_count = len(list(self._data_dir.rglob("*.csv")))
        if csv_count > 0:
            logger.info(f"NSE-Data directory ready: {self._data_dir} ({csv_count} CSVs)")
        else:
            logger.warning(
                f"No CSV files found in {self._data_dir}. "
                f"Download NSE-Data CSVs from GitHub (debaonline4u/NSE-Data) "
                f"and place them here. Expected structure: {self._data_dir}/5 Minutes/RELIANCE.csv"
            )

    async def disconnect(self) -> None:
        pass

    def _find_csv(self, symbol: str, interval: str) -> Path | None:
        if not self._data_dir:
            return None

        clean = symbol.replace(".NS", "").replace("-EQ", "").upper()
        folder_name = INTERVAL_FOLDER_MAP.get(interval, "Daily")

        search_paths = [
            self._data_dir / folder_name / f"{clean}.csv",
            self._data_dir / folder_name / f"{clean}_data.csv",
            self._data_dir / f"{clean}_{folder_name}.csv",
            self._data_dir / f"{clean}.csv",
        ]

        for p in search_paths:
            if p.exists():
                return p

        for p in self._data_dir.rglob(f"*{clean}*.csv"):
            parent_name = p.parent.name.lower()
            if folder_name.lower() in parent_name or interval in parent_name:
                return p

        for p in self._data_dir.rglob(f"*{clean}*.csv"):
            return p

        return None

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date | datetime,
        end_date: date | datetime,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        csv_path = self._find_csv(symbol, interval)
        if not csv_path:
            return []

        loop = asyncio.get_event_loop()

        def _parse():
            import pandas as pd

            try:
                df = pd.read_csv(csv_path)
            except Exception as e:
                logger.warning(f"Failed to read {csv_path}: {e}")
                return []

            col_map = {}
            for col in df.columns:
                cl = col.strip().lower()
                if cl in ("date", "datetime", "date/time", "timestamp", "time"):
                    col_map["date"] = col
                elif cl == "open":
                    col_map["open"] = col
                elif cl == "high":
                    col_map["high"] = col
                elif cl == "low":
                    col_map["low"] = col
                elif cl in ("close", "ltp"):
                    col_map["close"] = col
                elif cl in ("volume", "vol", "traded qty"):
                    col_map["volume"] = col

            if "date" not in col_map or "close" not in col_map:
                logger.warning(f"CSV {csv_path} missing date/close columns: {list(df.columns)}")
                return []

            df["_parsed_date"] = pd.to_datetime(df[col_map["date"]], errors="coerce", dayfirst=True)
            df = df.dropna(subset=["_parsed_date"])

            sd = pd.Timestamp(start_date).tz_localize(None) if hasattr(start_date, 'tzinfo') and start_date.tzinfo else pd.Timestamp(start_date)
            ed = pd.Timestamp(end_date).tz_localize(None) if hasattr(end_date, 'tzinfo') and end_date.tzinfo else pd.Timestamp(end_date)
            df["_parsed_date"] = df["_parsed_date"].dt.tz_localize(None)
            mask = (df["_parsed_date"] >= sd) & (df["_parsed_date"] <= ed)
            df = df[mask]

            results = []
            for _, row in df.iterrows():
                dt = row["_parsed_date"].to_pydatetime().replace(tzinfo=timezone.utc)
                results.append({
                    "date": dt,
                    "open": float(row.get(col_map.get("open", ""), 0) or 0),
                    "high": float(row.get(col_map.get("high", ""), 0) or 0),
                    "low": float(row.get(col_map.get("low", ""), 0) or 0),
                    "close": float(row[col_map["close"]]),
                    "volume": float(row.get(col_map.get("volume", ""), 0) or 0),
                })
            return results

        return await loop.run_in_executor(None, _parse)

    async def fetch_instruments(self, exchange: str | None = None) -> list[dict[str, Any]]:
        all_symbols = NIFTY_50 + NIFTY_NEXT_50
        result = []
        for sym in all_symbols:
            result.append({
                "symbol": sym,
                "name": sym,
                "asset_type": "equity",
                "exchange": "NSE",
                "currency": "INR",
            })
        return result

    async def search_symbol(self, query: str) -> list[dict[str, Any]]:
        clean = query.upper().replace(".NS", "").replace("-EQ", "")
        all_symbols = NIFTY_50 + NIFTY_NEXT_50
        return [
            {"symbol": s, "name": s, "asset_type": "equity", "exchange": "NSE"}
            for s in all_symbols if clean in s
        ]
