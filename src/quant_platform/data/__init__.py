"""Data ingestion, backtesting, scoring, and data providers."""

from .ingestion import ingestion_service, IngestionService
from .backtesting import BacktestEngine, BacktestResult
from .scoring import score_strategy, rank_strategies, StrategyScore
from .yfinance_provider import YFinanceProvider
from .nse_provider import NSEProvider
from .crypto_provider import CryptoProvider
from ..plugins.data_provider import DataProvider

__all__ = [
    "ingestion_service", "IngestionService",
    "BacktestEngine", "BacktestResult",
    "score_strategy", "rank_strategies", "StrategyScore",
    "DataProvider", "YFinanceProvider", "NSEProvider", "CryptoProvider",
]
