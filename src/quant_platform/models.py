"""SQLAlchemy ORM models and Pydantic schemas for the quant platform."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Enums ---

class AssetType(str, Enum):
    EQUITY = "equity"
    INDEX = "index"
    FUTURES = "futures"
    OPTIONS = "options"
    CRYPTO = "crypto"
    COMMODITY = "commodity"


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


class StrategyStatus(str, Enum):
    DISCOVERED = "discovered"
    BACKTESTING = "backtesting"
    SCORED = "scored"
    SHORTLISTED = "shortlisted"
    PAPER_TRADING = "paper_trading"
    PROMOTED = "promoted"
    DEMOTED = "demoted"
    RETIRED = "retired"


# --- SQLAlchemy ORM Models ---

class AssetORM(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    asset_type = Column(String(20), nullable=False, default="equity")
    exchange = Column(String(20), nullable=False, default="NSE")
    market_profile = Column(String(50), nullable=False, default="nse_equity")
    currency = Column(String(10), nullable=False, default="INR")
    lot_size = Column(Integer, nullable=False, default=1)
    tick_size = Column(Float, nullable=False, default=0.05)
    sector = Column(String(100))
    market_cap_category = Column(String(20))
    expiry_date = Column(DateTime, nullable=True)
    strike_price = Column(Float, nullable=True)
    option_type = Column(String(10), nullable=True)
    contract_type = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("symbol", "exchange", "asset_type", name="uq_asset_symbol_exchange_type"),
        Index("ix_asset_market_profile", "market_profile"),
        Index("ix_asset_exchange", "exchange"),
    )

    ohlcv = relationship("OHLCVORM", back_populates="asset", cascade="all, delete-orphan")
    positions = relationship("PositionORM", back_populates="asset")
    trades = relationship("TradeORM", back_populates="asset")


class OHLCVORM(Base):
    __tablename__ = "ohlcv"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    adj_close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("asset_id", "date", name="uq_ohlcv_asset_date"),
        Index("ix_ohlcv_date", "date"),
        Index("ix_ohlcv_asset_date", "asset_id", "date"),
    )

    asset = relationship("AssetORM", back_populates="ohlcv")


class PortfolioORM(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, default="")
    initial_capital = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="INR")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    positions = relationship("PositionORM", back_populates="portfolio", cascade="all, delete-orphan")
    trades = relationship("TradeORM", back_populates="portfolio", cascade="all, delete-orphan")


class PositionORM(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    quantity = Column(Float, nullable=False, default=0.0)
    avg_entry_price = Column(Float, nullable=False, default=0.0)
    current_price = Column(Float, nullable=False, default=0.0)
    side = Column(String(10), nullable=False, default="long")
    status = Column(String(10), nullable=False, default="open")
    opened_at = Column(DateTime, nullable=False, default=_utcnow)
    closed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_position_status", "status"),
    )

    portfolio = relationship("PortfolioORM", back_populates="positions")
    asset = relationship("AssetORM", back_populates="positions")
    strategy = relationship("StrategyORM", back_populates="positions")
    trades = relationship("TradeORM", back_populates="position")


class TradeORM(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    side = Column(String(10), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    commission = Column(Float, nullable=False, default=0.0)
    slippage = Column(Float, nullable=False, default=0.0)
    order_type = Column(String(10), nullable=False, default="market")
    is_simulated = Column(Boolean, nullable=False, default=True)
    executed_at = Column(DateTime, nullable=False, default=_utcnow)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    notes = Column(Text, default="")

    __table_args__ = (
        Index("ix_trade_executed", "executed_at"),
        Index("ix_trade_strategy", "strategy_id"),
    )

    portfolio = relationship("PortfolioORM", back_populates="trades")
    asset = relationship("AssetORM", back_populates="trades")
    position = relationship("PositionORM", back_populates="trades")
    strategy = relationship("StrategyORM", back_populates="trades")


class StrategyORM(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, default="")
    source = Column(String(50), nullable=False, default="manual")
    source_ref = Column(String(500))
    version = Column(String(20), nullable=False, default="1.0")
    parameters = Column(Text, default="{}")
    status = Column(String(20), nullable=False, default="discovered")
    win_rate = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    profit_factor = Column(Float)
    net_profit_after_fees = Column(Float)
    optimal_position_size = Column(Float)
    optimal_stop_loss = Column(Float)
    is_original = Column(Boolean, nullable=False, default=False)
    is_publishable = Column(Boolean, nullable=False, default=False)
    parent_strategy_ids = Column(Text)
    generation = Column(Integer, default=0)
    lineage_path = Column(Text)
    pine_script = Column(Text)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_strategy_status", "status"),
        Index("ix_strategy_source", "source"),
    )

    positions = relationship("PositionORM", back_populates="strategy")
    trades = relationship("TradeORM", back_populates="strategy")
    backtests = relationship("BacktestResultORM", back_populates="strategy", cascade="all, delete-orphan")


class BacktestResultORM(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    total_trades = Column(Integer, nullable=False, default=0)
    winning_trades = Column(Integer, nullable=False, default=0)
    losing_trades = Column(Integer, nullable=False, default=0)
    win_rate = Column(Float)
    gross_profit = Column(Float)
    total_fees = Column(Float, default=0.0)
    net_profit = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    profit_factor = Column(Float)
    avg_trade_pnl = Column(Float)
    parameters_used = Column(Text, default="{}")
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    __table_args__ = (
        Index("ix_backtest_strategy", "strategy_id"),
    )

    strategy = relationship("StrategyORM", back_populates="backtests")
    asset = relationship("AssetORM")


class KillSwitchStateORM(Base):
    __tablename__ = "kill_switch_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    is_active = Column(Boolean, nullable=False, default=False)
    triggered_by = Column(String(50))
    triggered_at = Column(DateTime)
    reason = Column(Text)
    last_heartbeat = Column(DateTime)


class SystemEventORM(Base):
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)
    source = Column(String(50), nullable=False)
    payload = Column(Text, default="{}")
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    __table_args__ = (
        Index("ix_event_type", "event_type"),
        Index("ix_event_created", "created_at"),
    )


# --- Pydantic Schemas (API layer) ---

class AssetSchema(BaseModel):
    id: int | None = None
    symbol: str
    name: str
    asset_type: AssetType = AssetType.EQUITY
    exchange: str = "NSE"
    market_profile: str = "nse_equity"
    currency: str = "INR"
    lot_size: int = Field(default=1, ge=1)
    tick_size: float = Field(default=0.05, gt=0)
    sector: str | None = None
    market_cap_category: str | None = None
    is_active: bool = True

    model_config = {"from_attributes": True}

    @field_validator("symbol")
    @classmethod
    def symbol_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("symbol must not be empty")
        return v.upper().strip()


class PortfolioSchema(BaseModel):
    id: int | None = None
    name: str
    description: str = ""
    initial_capital: float = Field(default=0.0, ge=0)
    currency: str = "INR"
    is_active: bool = True

    model_config = {"from_attributes": True}

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v.strip()


class PositionSchema(BaseModel):
    id: int | None = None
    portfolio_id: int
    asset_id: int
    strategy_id: int | None = None
    quantity: float = 0.0
    avg_entry_price: float = Field(default=0.0, ge=0)
    current_price: float = Field(default=0.0, ge=0)
    side: Side = Side.LONG
    status: PositionStatus = PositionStatus.OPEN

    model_config = {"from_attributes": True}

    @property
    def unrealized_pnl(self) -> float:
        multiplier = 1.0 if self.side == Side.LONG else -1.0
        return multiplier * self.quantity * (self.current_price - self.avg_entry_price)

    @property
    def market_value(self) -> float:
        return abs(self.quantity) * self.current_price


class TradeSchema(BaseModel):
    id: int | None = None
    portfolio_id: int
    asset_id: int
    position_id: int | None = None
    strategy_id: int | None = None
    side: Side
    quantity: float = Field(gt=0)
    price: float = Field(ge=0)
    commission: float = Field(default=0.0, ge=0)
    slippage: float = Field(default=0.0, ge=0)
    order_type: OrderType = OrderType.MARKET
    is_simulated: bool = True
    notes: str = ""

    model_config = {"from_attributes": True}

    @property
    def total_cost(self) -> float:
        return (self.quantity * self.price) + self.commission + self.slippage


class StrategySchema(BaseModel):
    id: int | None = None
    name: str
    description: str = ""
    source: str = "manual"
    source_ref: str | None = None
    version: str = "1.0"
    parameters: str = "{}"
    status: StrategyStatus = StrategyStatus.DISCOVERED
    win_rate: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    profit_factor: float | None = None
    net_profit_after_fees: float | None = None
    optimal_position_size: float | None = None
    optimal_stop_loss: float | None = None
    is_original: bool = False
    is_publishable: bool = False

    model_config = {"from_attributes": True}
