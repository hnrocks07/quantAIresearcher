"""Autonomous research engine — discovers, backtests, and scores strategies without intervention."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..database import get_db
from ..models import AssetORM, OHLCVORM, StrategyORM, StrategyStatus
from ..data.backtesting import BacktestEngine, BacktestResult
from ..data.scoring import score_strategy, rank_strategies, PROMOTION_THRESHOLD
from ..plugins.broker import FeeSchedule
from ..market_profiles import load_profile
from ..event_bus import event_bus
from ..logging import get_logger
from .strategies import BUILTIN_STRATEGIES, PARAMETER_GRID, SignalResult

logger = get_logger("research")


class ResearchStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ResearchEngine:

    def __init__(self):
        self._status = ResearchStatus.IDLE
        self._started_at: float | None = None
        self._completed_at: float | None = None
        self._strategies_tested: int = 0
        self._strategies_shortlisted: int = 0
        self._backtests_run: int = 0
        self._errors: list[dict[str, Any]] = []
        self._current_work: str = ""
        self._stop_requested: bool = False
        self._task: asyncio.Task | None = None

    def status(self) -> dict[str, Any]:
        elapsed = 0.0
        if self._started_at:
            end = self._completed_at or time.monotonic()
            elapsed = round(end - self._started_at, 1)
        return {
            "status": self._status.value,
            "strategies_tested": self._strategies_tested,
            "strategies_shortlisted": self._strategies_shortlisted,
            "backtests_run": self._backtests_run,
            "errors_count": len(self._errors),
            "current_work": self._current_work,
            "elapsed_seconds": elapsed,
        }

    def errors(self) -> list[dict[str, Any]]:
        return self._errors[-100:]

    async def start(self, profile_name: str = "nse_equity", top_n_assets: int = 50) -> dict[str, str]:
        if self._status == ResearchStatus.RUNNING:
            return {"error": "Already running"}

        self._status = ResearchStatus.RUNNING
        self._started_at = time.monotonic()
        self._completed_at = None
        self._strategies_tested = 0
        self._strategies_shortlisted = 0
        self._backtests_run = 0
        self._errors = []
        self._stop_requested = False

        self._task = asyncio.create_task(self._run(profile_name, top_n_assets))
        return {"status": "started", "profile": profile_name}

    async def stop(self) -> dict[str, str]:
        self._stop_requested = True
        return {"status": "stop_requested"}

    async def _run(self, profile_name: str, top_n_assets: int) -> None:
        try:
            profile = load_profile(profile_name)
            fee_schedule = FeeSchedule(**profile.fee_defaults)
            engine = BacktestEngine(fee_schedule=fee_schedule)

            await event_bus.emit("research.started", "research", profile=profile_name)
            logger.info(f"Research started for {profile_name}")

            with get_db() as db:
                assets = db.query(AssetORM).filter(
                    AssetORM.market_profile == profile_name,
                    AssetORM.is_active == True,
                ).limit(top_n_assets).all()
                asset_ids = [(a.id, a.symbol) for a in assets]

            if not asset_ids:
                logger.warning("No assets found for research — run ingestion first")
                self._status = ResearchStatus.COMPLETED
                self._completed_at = time.monotonic()
                return

            for strat_name, strat_func in BUILTIN_STRATEGIES.items():
                if self._stop_requested:
                    break

                param_sets = PARAMETER_GRID.get(strat_name, [{}])
                for params in param_sets:
                    if self._stop_requested:
                        break

                    full_name = f"{strat_name}_{json.dumps(params, sort_keys=True)}"
                    self._current_work = full_name

                    strategy_id = self._ensure_strategy(strat_name, params, full_name)

                    for asset_id, symbol in asset_ids:
                        if self._stop_requested:
                            break

                        try:
                            self._run_single_backtest(
                                engine, strat_func, params, strategy_id, asset_id, symbol
                            )
                            self._backtests_run += 1
                        except Exception as e:
                            self._errors.append({
                                "strategy": full_name,
                                "symbol": symbol,
                                "error": str(e),
                            })

                    score = score_strategy(strategy_id)
                    if score and score.win_rate >= PROMOTION_THRESHOLD and score.is_fee_profitable:
                        self._strategies_shortlisted += 1

                    self._strategies_tested += 1

                    if self._strategies_tested % 5 == 0:
                        logger.info(f"Research progress: {self._strategies_tested} strategies, {self._backtests_run} backtests")

            self._status = ResearchStatus.STOPPED if self._stop_requested else ResearchStatus.COMPLETED
            self._completed_at = time.monotonic()
            await event_bus.emit("research.completed", "research",
                                tested=self._strategies_tested,
                                shortlisted=self._strategies_shortlisted,
                                backtests=self._backtests_run)
            logger.info(f"Research complete: {self._strategies_tested} strategies, {self._strategies_shortlisted} shortlisted")

        except Exception as e:
            self._status = ResearchStatus.FAILED
            self._completed_at = time.monotonic()
            logger.error(f"Research failed: {e}")
            self._errors.append({"error": str(e), "fatal": True})

    def _ensure_strategy(self, base_name: str, params: dict, full_name: str) -> int:
        with get_db() as db:
            existing = db.query(StrategyORM).filter(StrategyORM.name == full_name).first()
            if existing:
                return existing.id

            strategy = StrategyORM(
                name=full_name,
                description=f"Auto-discovered {base_name} strategy",
                source="research_engine",
                version="1.0",
                parameters=json.dumps(params),
                status=StrategyStatus.BACKTESTING.value,
            )
            db.add(strategy)
            db.flush()
            return strategy.id

    def _run_single_backtest(
        self,
        engine: BacktestEngine,
        strat_func,
        params: dict,
        strategy_id: int,
        asset_id: int,
        symbol: str,
    ) -> BacktestResult:
        with get_db() as db:
            rows = db.query(OHLCVORM).filter(
                OHLCVORM.asset_id == asset_id
            ).order_by(OHLCVORM.date.asc()).all()

        if len(rows) < 60:
            return BacktestResult()

        prices = [r.close for r in rows]
        dates = [r.date for r in rows]

        signals = strat_func(prices, **params)

        result = engine.run_signal_backtest(
            prices=prices,
            dates=dates,
            entries=signals.entries,
            exits=signals.exits,
        )

        if result.total_trades > 0:
            engine.save_result(
                result=result,
                strategy_id=strategy_id,
                asset_id=asset_id,
                start_date=dates[0],
                end_date=dates[-1],
                parameters_used=json.dumps(params),
            )

            with get_db() as db:
                s = db.query(StrategyORM).filter(StrategyORM.id == strategy_id).first()
                if s and s.status == StrategyStatus.BACKTESTING.value:
                    s.status = StrategyStatus.SCORED.value
                    db.flush()

        return result


research_engine = ResearchEngine()
