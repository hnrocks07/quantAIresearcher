"""Autonomous research engine — discovers, backtests, and scores strategies without intervention."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..config import get_settings, RunMode
from ..database import get_db
from ..models import AssetORM, OHLCVORM, StrategyORM, StrategyStatus
from ..data.backtesting import BacktestEngine, BacktestResult
from ..data.scoring import score_strategy, rank_strategies, PROMOTION_THRESHOLD
from ..plugins.broker import FeeSchedule
from ..market_profiles import load_profile
from ..event_bus import event_bus
from ..logging import get_logger
from .strategies import BUILTIN_STRATEGIES, PARAMETER_GRID, SignalResult
from .position_sizing import calculate_position_size
from .stop_loss import calculate_optimal_sl
from .regime import classify_regime
from .combination import combine_strategies, generate_combinations, BestOfBestFinder, combine_three
from .lineage import record_lineage
from .pine_export import export_to_pine
from .activity_log import activity_log

logger = get_logger("research")

_TV_SOURCE = None
try:
    from .tradingview_source import TradingViewSource
    _TV_SOURCE = TradingViewSource
except Exception:
    pass


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

    async def start(self, profile_name: str = "nse_equity", top_n_assets: int = 50, source_mode: str = "builtin") -> dict[str, str]:
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
        self._source_mode = source_mode

        self._task = asyncio.create_task(self._run(profile_name, top_n_assets))
        return {"status": "started", "profile": profile_name, "source_mode": source_mode}

    async def stop(self) -> dict[str, str]:
        self._stop_requested = True
        return {"status": "stop_requested"}

    async def _run(self, profile_name: str, top_n_assets: int) -> None:
        settings = get_settings()
        source_mode = getattr(self, "_source_mode", "builtin")

        try:
            while True:
                profile = load_profile(profile_name)
                fee_schedule = FeeSchedule(**profile.fee_defaults)
                engine = BacktestEngine(fee_schedule=fee_schedule)

                await event_bus.emit("research.started", "research", profile=profile_name)
                logger.info(f"Research started for {profile_name}")
                activity_log.log_action("research_started", profile_name, f"source_mode={source_mode}")

                # TradingView auto-discovery: pull community strategies + multi-TF signals
                if source_mode in ("tradingview", "both") and _TV_SOURCE:
                    try:
                        tv = _TV_SOURCE(
                            username=settings.tradingview_username,
                            password=settings.tradingview_password,
                        )
                        await tv.connect()
                        imported = await tv.discover_strategies(limit=50)
                        for imp in imported:
                            params = imp.parameters if isinstance(imp.parameters, dict) else {}
                            self._ensure_strategy(
                                imp.name, params, imp.name, source=imp.source or "tradingview"
                            )
                            activity_log.log_action(
                                "tv_strategy_imported", imp.name,
                                f"source={imp.source}, type={params.get('type', 'unknown')}",
                                reasoning=imp.description,
                            )
                        await tv.disconnect()
                        logger.info(f"TradingView discovery: {len(imported)} strategies imported")
                    except Exception as e:
                        logger.warning(f"TradingView discovery failed, falling back: {e}")
                        self._errors.append({"source": "tradingview", "error": str(e)})

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

                if source_mode in ("builtin", "both"):
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
                            activity_log.log_action("backtest_start", full_name, f"assets={len(asset_ids)}")

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
                                activity_log.log_action("shortlisted", full_name, f"win_rate={score.win_rate}")

                                # Position sizing and stop loss for winners
                                self._enrich_winner(strategy_id, asset_ids, strat_name, params)

                            self._strategies_tested += 1

                            if self._strategies_tested % 5 == 0:
                                logger.info(f"Research progress: {self._strategies_tested} strategies, {self._backtests_run} backtests")

                # Try combining top strategies
                if not self._stop_requested:
                    self._try_combinations(engine, asset_ids)

                await event_bus.emit("research.completed", "research",
                                    tested=self._strategies_tested,
                                    shortlisted=self._strategies_shortlisted,
                                    backtests=self._backtests_run)
                logger.info(f"Research cycle complete: {self._strategies_tested} strategies, {self._strategies_shortlisted} shortlisted")

                if self._stop_requested:
                    self._status = ResearchStatus.STOPPED
                    self._completed_at = time.monotonic()
                    return

                if settings.run_mode == RunMode.LOCAL:
                    self._status = ResearchStatus.COMPLETED
                    self._completed_at = time.monotonic()
                    return

                logger.info(f"Server mode: sleeping {settings.research_interval_minutes} minutes before next research cycle")
                self._current_work = "sleeping_between_cycles"
                await asyncio.sleep(settings.research_interval_minutes * 60)

        except Exception as e:
            self._status = ResearchStatus.FAILED
            self._completed_at = time.monotonic()
            logger.error(f"Research failed: {e}")
            self._errors.append({"error": str(e), "fatal": True})

    def _enrich_winner(self, strategy_id: int, asset_ids: list, strat_name: str, params: dict) -> None:
        try:
            with get_db() as db:
                first_asset = asset_ids[0][0] if asset_ids else None
                if not first_asset:
                    return
                rows = db.query(OHLCVORM).filter(
                    OHLCVORM.asset_id == first_asset
                ).order_by(OHLCVORM.date.asc()).all()

            if len(rows) < 20:
                return
            prices = [r.close for r in rows]

            ps = calculate_position_size(prices, 100000.0)
            sl = calculate_optimal_sl(prices)

            # Generate pine script
            pine_type_map = {
                "sma_crossover": "sma_crossover",
                "rsi_reversal": "rsi",
                "macd_signal": "macd",
                "bollinger_breakout": "bollinger",
                "mean_reversion": "mean_reversion",
            }
            pine_type = pine_type_map.get(strat_name, "sma_crossover")
            pine = export_to_pine(strat_name, params, pine_type)

            with get_db() as db:
                s = db.query(StrategyORM).filter(StrategyORM.id == strategy_id).first()
                if s:
                    s.optimal_position_size = float(ps["position_size"])
                    s.optimal_stop_loss = sl["sl_pct"]
                    s.pine_script = pine
                    db.flush()

            activity_log.log_action("enriched", strat_name, f"pos_size={ps['position_size']}, sl={sl['sl_pct']}")
        except Exception as e:
            logger.warning(f"Failed to enrich winner {strat_name}: {e}")

    def _try_combinations(self, engine: BacktestEngine, asset_ids: list) -> None:
        """Find best-of-best by combining all winning strategies (2-way and 3-way)."""
        try:
            if not asset_ids:
                return

            first_asset = asset_ids[0][0]
            with get_db() as db:
                rows = db.query(OHLCVORM).filter(
                    OHLCVORM.asset_id == first_asset
                ).order_by(OHLCVORM.date.asc()).all()

            if len(rows) < 60:
                return
            prices = [r.close for r in rows]
            dates = [r.date for r in rows]

            winners = {}
            with get_db() as db:
                scored = db.query(StrategyORM).filter(
                    StrategyORM.status.in_(["scored", "shortlisted", "paper_trading", "promoted"])
                ).all()
                for s in scored:
                    base_name = s.name.split("_")[0] if "_" in s.name else s.name
                    if base_name in BUILTIN_STRATEGIES:
                        try:
                            params = json.loads(s.parameters) if s.parameters else {}
                        except (json.JSONDecodeError, TypeError):
                            params = {}
                        winners[s.name] = {
                            "params": params,
                            "win_rate": s.win_rate or 0,
                            "sharpe": s.sharpe_ratio or 0,
                            "base_name": base_name,
                        }

            if len(winners) < 2:
                all_combos = generate_combinations(BUILTIN_STRATEGIES, max_ways=2)
                for name_a, name_b in all_combos:
                    try:
                        sig_a = BUILTIN_STRATEGIES[name_a](prices)
                        sig_b = BUILTIN_STRATEGIES[name_b](prices)
                        for mode in ("and", "or"):
                            combined = combine_strategies(sig_a, sig_b, mode=mode)
                            result = engine.run_signal_backtest(
                                prices=prices[:len(combined.entries)],
                                dates=dates[:len(combined.entries)],
                                entries=combined.entries, exits=combined.exits,
                            )
                            if result.total_trades > 0 and result.net_profit > 0:
                                combo_name = f"combo_{name_a}_{name_b}_{mode}"
                                self._ensure_strategy(combo_name, {"a": name_a, "b": name_b, "mode": mode}, combo_name)
                                activity_log.log_action("combination_tested", combo_name,
                                    f"trades={result.total_trades}, pnl={result.net_profit:.2f}, wr={result.win_rate:.2%}")
                    except Exception as e:
                        logger.debug(f"Combo {name_a}+{name_b} failed: {e}")
                return

            func_map = {}
            for name, info in winners.items():
                base = info["base_name"]
                if base in BUILTIN_STRATEGIES:
                    func_map[name] = lambda p, _b=base, _pr=info["params"]: BUILTIN_STRATEGIES[_b](p, **_pr)

            finder = BestOfBestFinder(engine)
            best = finder.find_best(
                winners=winners, prices=prices, dates=dates,
                strategy_funcs=func_map, top_n=10, include_triples=True,
            )

            for combo in best:
                combo_name = f"best_{combo['name']}"
                params = {"components": combo["components"], "mode": combo["mode"],
                          "win_rate": combo["win_rate"], "sharpe": combo["sharpe"],
                          "beats_all": combo.get("beats_all_components", False)}
                self._ensure_strategy(combo_name, params, combo_name, source="combination_engine")
                activity_log.log_action(
                    "best_of_best_found", combo_name,
                    f"wr={combo['win_rate']:.2%}, sharpe={combo['sharpe']:.2f}, "
                    f"trades={combo['total_trades']}, beats_all={combo.get('beats_all_components')}",
                    reasoning=f"Score {combo['score']:.1f}/100, components: {combo['components']}",
                )

            for combo in best:
                try:
                    record_lineage(f"best_{combo['name']}", combo["components"])
                except Exception:
                    pass

            if best:
                logger.info(f"Best-of-best: {best[0]['name']} (wr={best[0]['win_rate']:.2%}, score={best[0]['score']:.1f})")

        except Exception as e:
            logger.warning(f"Combination testing failed: {e}")

    def _ensure_strategy(self, base_name: str, params: dict, full_name: str, source: str = "research_engine") -> int:
        with get_db() as db:
            existing = db.query(StrategyORM).filter(StrategyORM.name == full_name).first()
            if existing:
                return existing.id

            strategy = StrategyORM(
                name=full_name,
                description=f"Auto-discovered {base_name} strategy",
                source=source,
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
