"""Core domain models: Asset, Portfolio, Position, Trade."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AssetType(str, Enum):
    EQUITY = "equity"
    INDEX = "index"
    FUTURES = "futures"
    OPTIONS = "options"


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"
    BUY = "buy"
    SELL = "sell"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class Asset(BaseModel):
    id: int | None = None
    symbol: str
    name: str
    asset_type: AssetType = AssetType.EQUITY
    exchange: str = "NSE"
    currency: str = "INR"
    lot_size: int = Field(default=1, ge=1)
    tick_size: float = Field(default=0.05, gt=0)
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @field_validator("symbol")
    @classmethod
    def symbol_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("symbol must not be empty")
        return v.upper().strip()


class Portfolio(BaseModel):
    id: int | None = None
    name: str
    description: str = ""
    initial_capital: float = Field(default=0.0, ge=0)
    currency: str = "INR"
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v.strip()


class Position(BaseModel):
    id: int | None = None
    portfolio_id: int
    asset_id: int
    quantity: float = 0.0
    avg_entry_price: float = Field(default=0.0, ge=0)
    current_price: float = Field(default=0.0, ge=0)
    side: Side = Side.LONG
    status: PositionStatus = PositionStatus.OPEN
    opened_at: datetime = Field(default_factory=_utcnow)
    closed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=_utcnow)

    @property
    def unrealized_pnl(self) -> float:
        multiplier = 1.0 if self.side == Side.LONG else -1.0
        return multiplier * self.quantity * (self.current_price - self.avg_entry_price)

    @property
    def market_value(self) -> float:
        return abs(self.quantity) * self.current_price


class Trade(BaseModel):
    id: int | None = None
    portfolio_id: int
    asset_id: int
    position_id: int | None = None
    side: Side
    quantity: float = Field(gt=0)
    price: float = Field(ge=0)
    commission: float = Field(default=0.0, ge=0)
    slippage: float = Field(default=0.0, ge=0)
    order_type: OrderType = OrderType.MARKET
    is_simulated: bool = True
    executed_at: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)
    notes: str = ""

    @field_validator("is_simulated")
    @classmethod
    def must_be_simulated(cls, v: bool) -> bool:
        if not v:
            raise ValueError("real trading is permanently disabled")
        return v

    @property
    def total_cost(self) -> float:
        return (self.quantity * self.price) + self.commission + self.slippage
