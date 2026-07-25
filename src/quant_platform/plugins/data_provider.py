"""DataProvider abstract interface — swap data sources via config."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any


class DataProvider(ABC):

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date | datetime,
        end_date: date | datetime,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        """Return list of dicts: {date, open, high, low, close, volume}."""
        ...

    @abstractmethod
    async def fetch_instruments(
        self, exchange: str | None = None
    ) -> list[dict[str, Any]]:
        """Return list of dicts with at minimum: {symbol, name, asset_type}.
        May also include: exchange, currency, sector, market_cap_category,
        expiry_date, strike_price, option_type, contract_type.
        """
        ...

    @abstractmethod
    async def search_symbol(self, query: str) -> list[dict[str, Any]]:
        """Search for a symbol, return matching instruments."""
        ...
