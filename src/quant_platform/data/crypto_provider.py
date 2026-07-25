"""Crypto data provider — fetches crypto OHLCV via yfinance with -USD suffix."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

from ..plugins.data_provider import DataProvider
from ..logging import get_logger

logger = get_logger("crypto_provider")

TOP_20_CRYPTOS = [
    {"symbol": "BTC", "name": "Bitcoin"},
    {"symbol": "ETH", "name": "Ethereum"},
    {"symbol": "BNB", "name": "Binance Coin"},
    {"symbol": "SOL", "name": "Solana"},
    {"symbol": "XRP", "name": "Ripple"},
    {"symbol": "ADA", "name": "Cardano"},
    {"symbol": "DOGE", "name": "Dogecoin"},
    {"symbol": "AVAX", "name": "Avalanche"},
    {"symbol": "DOT", "name": "Polkadot"},
    {"symbol": "MATIC", "name": "Polygon"},
    {"symbol": "LINK", "name": "Chainlink"},
    {"symbol": "UNI", "name": "Uniswap"},
    {"symbol": "ATOM", "name": "Cosmos"},
    {"symbol": "LTC", "name": "Litecoin"},
    {"symbol": "BCH", "name": "Bitcoin Cash"},
    {"symbol": "FIL", "name": "Filecoin"},
    {"symbol": "APT", "name": "Aptos"},
    {"symbol": "ARB", "name": "Arbitrum"},
    {"symbol": "OP", "name": "Optimism"},
    {"symbol": "INJ", "name": "Injective"},
]


class CryptoProvider(DataProvider):

    def name(self) -> str:
        return "crypto"

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    def _to_yf_symbol(self, symbol: str) -> str:
        clean = symbol.upper().replace("-USD", "")
        return f"{clean}-USD"

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date | datetime,
        end_date: date | datetime,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        import yfinance as yf

        yf_symbol = self._to_yf_symbol(symbol)
        start_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else str(start_date)
        end_str = end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else str(end_date)

        loop = asyncio.get_event_loop()

        def _download():
            ticker = yf.Ticker(yf_symbol)
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
        return [
            {
                "symbol": f"{c['symbol']}-USD",
                "name": c["name"],
                "asset_type": "crypto",
                "exchange": "CRYPTO",
                "currency": "USD",
            }
            for c in TOP_20_CRYPTOS
        ]

    async def search_symbol(self, query: str) -> list[dict[str, Any]]:
        query_upper = query.upper().replace("-USD", "")
        instruments = await self.fetch_instruments()
        return [
            inst for inst in instruments
            if query_upper in inst["symbol"].upper().replace("-USD", "")
            or query_upper in inst["name"].upper()
        ]
