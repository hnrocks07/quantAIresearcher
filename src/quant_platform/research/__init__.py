"""Autonomous research engine — discovers, backtests, scores strategies."""

from .engine import ResearchEngine, research_engine
from .tradingview_source import TradingViewSource
from .tradingview_webhook import process_webhook
from .position_sizing import calculate_position_size
from .stop_loss import calculate_optimal_sl
from .regime import classify_regime, classify_history
from .combination import combine_strategies, generate_combinations
from .pine_export import export_to_pine
from .activity_log import ResearchActivityLog, activity_log

__all__ = [
    "ResearchEngine", "research_engine",
    "TradingViewSource", "process_webhook",
    "calculate_position_size", "calculate_optimal_sl",
    "classify_regime", "classify_history",
    "combine_strategies", "generate_combinations",
    "export_to_pine",
    "ResearchActivityLog", "activity_log",
]
