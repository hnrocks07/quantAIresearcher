"""TradingView research source — TA_Handler-based strategy discovery."""

from __future__ import annotations

import logging
from typing import Any

from ..plugins.research import ResearchSource, ImportedStrategy
from ..database import get_db
from ..models import StrategyORM

logger = logging.getLogger("tradingview_source")

_TV_AVAILABLE = True
try:
    from tradingview_ta import TA_Handler, Interval
except ImportError:
    _TV_AVAILABLE = False
    logger.warning("tradingview_ta not installed, TradingViewSource will be limited")

DEFAULT_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "SBIN", "BHARTIARTL", "KOTAKBANK", "ITC",
]


class TradingViewSource(ResearchSource):

    def name(self) -> str:
        return "tradingview"

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def discover_strategies(self, limit: int = 50) -> list[ImportedStrategy]:
        if not _TV_AVAILABLE:
            logger.warning("tradingview_ta not installed, returning empty")
            return []

        results = []
        symbols = DEFAULT_SYMBOLS[:limit]
        for symbol in symbols:
            try:
                handler = TA_Handler(
                    symbol=symbol,
                    screener="india",
                    exchange="NSE",
                    interval=Interval.INTERVAL_1_DAY,
                )
                analysis = handler.get_analysis()
                summary = analysis.summary
                results.append(ImportedStrategy(
                    name=f"tv_{symbol}_daily",
                    source="tradingview",
                    source_ref=f"{symbol}:1D",
                    description=f"TradingView analysis for {symbol}",
                    parameters={
                        "recommendation": summary.get("RECOMMENDATION", "NEUTRAL"),
                        "buy": summary.get("BUY", 0),
                        "sell": summary.get("SELL", 0),
                        "neutral": summary.get("NEUTRAL", 0),
                    },
                ))
            except Exception as e:
                logger.warning(f"Failed to get analysis for {symbol}: {e}")

        return results

    async def get_strategy_details(self, source_ref: str) -> ImportedStrategy | None:
        if not _TV_AVAILABLE:
            return None

        try:
            parts = source_ref.split(":")
            symbol = parts[0]
            interval = parts[1] if len(parts) > 1 else "1D"

            interval_map = {
                "1m": Interval.INTERVAL_1_MINUTE,
                "5m": Interval.INTERVAL_5_MINUTES,
                "15m": Interval.INTERVAL_15_MINUTES,
                "1h": Interval.INTERVAL_1_HOUR,
                "4h": Interval.INTERVAL_4_HOURS,
                "1D": Interval.INTERVAL_1_DAY,
                "1W": Interval.INTERVAL_1_WEEK,
                "1M": Interval.INTERVAL_1_MONTH,
            }
            tv_interval = interval_map.get(interval, Interval.INTERVAL_1_DAY)

            handler = TA_Handler(
                symbol=symbol,
                screener="india",
                exchange="NSE",
                interval=tv_interval,
            )
            analysis = handler.get_analysis()
            return ImportedStrategy(
                name=f"tv_{symbol}_{interval}",
                source="tradingview",
                source_ref=source_ref,
                description=f"TradingView {interval} analysis for {symbol}",
                parameters={
                    "recommendation": analysis.summary.get("RECOMMENDATION", "NEUTRAL"),
                    "buy": analysis.summary.get("BUY", 0),
                    "sell": analysis.summary.get("SELL", 0),
                    "neutral": analysis.summary.get("NEUTRAL", 0),
                    "oscillators": analysis.oscillators,
                    "moving_averages": analysis.moving_averages,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to get details for {source_ref}: {e}")
            return None

    async def get_alerts(self) -> list[dict[str, Any]]:
        with get_db() as db:
            strategies = db.query(StrategyORM).filter(
                StrategyORM.source == "tradingview"
            ).all()
            return [
                {"id": s.id, "name": s.name, "status": s.status, "parameters": s.parameters}
                for s in strategies
            ]
