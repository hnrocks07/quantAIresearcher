"""YFinance data provider — wraps yfinance for OHLCV and instrument data."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

from ..plugins.data_provider import DataProvider
from ..logging import get_logger

logger = get_logger("yfinance_provider")


class YFinanceProvider(DataProvider):

    def name(self) -> str:
        return "yfinance"

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date | datetime,
        end_date: date | datetime,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        import yfinance as yf

        start_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else str(start_date)
        end_str = end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else str(end_date)

        loop = asyncio.get_event_loop()

        def _download():
            ticker = yf.Ticker(symbol)
            return ticker.history(start=start_str, end=end_str, auto_adjust=False)

        df = await loop.run_in_executor(None, _download)

        if df is None or df.empty:
            return []

        result = []
        for idx, row in df.iterrows():
            dt = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
            result.append({
                "date": dt,
                "open": float(row.get("Open", 0)),
                "high": float(row.get("High", 0)),
                "low": float(row.get("Low", 0)),
                "close": float(row.get("Close", 0)),
                "volume": float(row.get("Volume", 0)),
            })
        return result

    async def fetch_instruments(
        self, exchange: str | None = None
    ) -> list[dict[str, Any]]:
        if exchange and exchange.upper() == "NSE":
            return await self._fetch_nifty500()
        return []

    async def _fetch_nifty500(self) -> list[dict[str, Any]]:
        try:
            import pandas as pd

            url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(None, lambda: pd.read_csv(url))
            result = []
            for _, row in df.iterrows():
                symbol = row.get("Symbol", "")
                name = row.get("Company Name", symbol)
                if symbol:
                    entry: dict[str, Any] = {
                        "symbol": f"{symbol}.NS",
                        "name": str(name),
                        "asset_type": "equity",
                        "exchange": "NSE",
                        "currency": "INR",
                    }
                    industry = row.get("Industry", "")
                    if industry:
                        entry["sector"] = str(industry)
                    result.append(entry)
            logger.info(f"Fetched NIFTY 500 list: {len(result)} stocks")
            return result
        except Exception as e:
            logger.warning(f"Could not fetch NIFTY 500 list: {e}")
            return []

    async def search_symbol(self, query: str) -> list[dict[str, Any]]:
        import yfinance as yf

        loop = asyncio.get_event_loop()

        def _search():
            try:
                ticker = yf.Ticker(query)
                info = ticker.info
                if info and info.get("symbol"):
                    return [{
                        "symbol": info.get("symbol", query),
                        "name": info.get("longName", info.get("shortName", query)),
                        "asset_type": "equity",
                        "exchange": info.get("exchange", ""),
                        "currency": info.get("currency", ""),
                    }]
            except Exception:
                pass
            return []

        return await loop.run_in_executor(None, _search)
