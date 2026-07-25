"""Trading executor — autonomous pipeline with all risk/agent/promotion components wired."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone, date
from enum import Enum
from typing import Any

from ..config import get_settings, RunMode
from ..database import get_db
from ..models import (
    StrategyORM, AssetORM, OHLCVORM, PortfolioORM, PositionORM, TradeORM,
    StrategyStatus, PositionStatus,
)
from ..plugins.broker import BrokerAdapter, FeeSchedule
from ..plugins.llm import LLMProvider
from ..kill_switch import kill_switch
from ..event_bus import event_bus
from ..logging import get_logger
from ..research.strategies import BUILTIN_STRATEGIES
from ..agents.activity_feed import activity_feed

logger = get_logger("trading_executor")


class ExecutorStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    KILLED = "killed"


class TradingExecutor:

    def __init__(self, llm_provider: LLMProvider | None = None):
        self._status = ExecutorStatus.IDLE
        self._broker: BrokerAdapter | None = None
        self._portfolio_id: int | None = None
        self._trades_executed: int = 0
        self._stop_requested: bool = False
        self._task: asyncio.Task | None = None
        self._cycle_count: int = 0
        self._llm_provider = llm_provider
        self._initial_capital: float = 1000000.0

    def status(self) -> dict[str, Any]:
        return {
            "status": self._status.value,
            "trades_executed": self._trades_executed,
            "cycle_count": self._cycle_count,
            "portfolio_id": self._portfolio_id,
            "broker": self._broker.name() if self._broker else None,
        }

    async def start(
        self,
        broker: BrokerAdapter,
        portfolio_name: str = "paper_trading",
        initial_capital: float = 1000000.0,
        interval_seconds: int = 60,
    ) -> dict[str, str]:
        if self._status == ExecutorStatus.RUNNING:
            return {"error": "Already running"}

        self._broker = broker
        self._initial_capital = initial_capital
        await broker.connect()

        with get_db() as db:
            portfolio = db.query(PortfolioORM).filter(PortfolioORM.name == portfolio_name).first()
            if not portfolio:
                portfolio = PortfolioORM(
                    name=portfolio_name,
                    description="Auto-created paper trading portfolio",
                    initial_capital=initial_capital,
                    currency="INR",
                )
                db.add(portfolio)
                db.flush()
            self._portfolio_id = portfolio.id

        self._status = ExecutorStatus.RUNNING
        self._stop_requested = False
        self._task = asyncio.create_task(self._run_loop(interval_seconds))
        return {"status": "started", "portfolio_id": self._portfolio_id}

    async def stop(self) -> dict[str, str]:
        self._stop_requested = True
        return {"status": "stop_requested"}

    async def _run_loop(self, interval: int, max_cycles: int = 0) -> None:
        settings = get_settings()

        if max_cycles == 0 and settings.run_mode == RunMode.LOCAL:
            max_cycles = 10

        try:
            while not self._stop_requested:
                try:
                    kill_switch.check_or_raise("execute_cycle")
                except RuntimeError:
                    self._status = ExecutorStatus.KILLED
                    logger.warning("Kill switch active — executor halted")
                    await event_bus.emit("trading.killed", "executor")
                    return

                # 1. Check daily loss BEFORE trading
                await self._check_daily_loss()

                # 2. Execute strategies
                await self._execute_cycle()
                self._cycle_count += 1

                # 3. Post-cycle: promotion/demotion check
                await self._run_promotion_check()

                # 4. Post-cycle: performance monitoring + review
                await self._run_performance_review()

                # 5. Post-cycle: strategy rotation
                await self._run_rotation()

                if max_cycles > 0 and self._cycle_count >= max_cycles:
                    logger.info(f"Local mode: completed {max_cycles} cycles, stopping")
                    break

                await asyncio.sleep(interval)

            self._status = ExecutorStatus.STOPPED
            logger.info("Executor stopped")

        except Exception as e:
            logger.error(f"Executor error: {e}")
            self._status = ExecutorStatus.STOPPED

    async def _check_daily_loss(self) -> None:
        """Check daily loss cap — triggers kill switch if breached."""
        try:
            from ..risk.daily_loss_monitor import DailyLossMonitor
            settings = get_settings()
            monitor = DailyLossMonitor(settings, kill_switch)

            with get_db() as db:
                today = date.today()
                trades_today = db.query(TradeORM).filter(
                    TradeORM.portfolio_id == self._portfolio_id,
                    TradeORM.created_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
                ).all()

            result = monitor.check(trades_today, self._initial_capital)
            if result["breached"]:
                activity_feed.log("daily_loss_monitor", "kill_switch_triggered",
                    {"pnl": result["pnl_today"], "loss_pct": result["loss_pct"], "cap": result["cap_pct"]},
                    reasoning="Daily loss cap exceeded — all trading halted")
                logger.warning(f"Daily loss cap breached: {result['loss_pct']:.2%} > {result['cap_pct']:.2%}")
        except Exception as e:
            logger.debug(f"Daily loss check error: {e}")

    async def _execute_cycle(self) -> None:
        settings = get_settings()

        with get_db() as db:
            shortlisted = db.query(StrategyORM).filter(
                StrategyORM.status.in_([
                    StrategyStatus.SHORTLISTED.value,
                    StrategyStatus.PAPER_TRADING.value,
                    StrategyStatus.PROMOTED.value,
                ])
            ).all()

        for strategy in shortlisted:
            try:
                await self._execute_strategy(strategy)
            except Exception as e:
                logger.warning(f"Strategy {strategy.name} execution error: {e}")

    async def _execute_strategy(self, strategy: StrategyORM) -> None:
        settings = get_settings()
        params = json.loads(strategy.parameters) if strategy.parameters else {}

        for name, func in BUILTIN_STRATEGIES.items():
            if strategy.name.startswith(name):
                strat_func = func
                break
        else:
            return

        with get_db() as db:
            assets = db.query(AssetORM).filter(AssetORM.is_active == True).limit(10).all()

        for asset in assets:
            with get_db() as db:
                rows = db.query(OHLCVORM).filter(
                    OHLCVORM.asset_id == asset.id
                ).order_by(OHLCVORM.date.desc()).limit(100).all()

            if len(rows) < 30:
                continue

            rows.reverse()
            prices = [r.close for r in rows]
            signals = strat_func(prices, **params)

            if signals.entries[-1]:
                # Position limit check
                allowed = await self._check_position_limits(asset.symbol)
                if not allowed:
                    activity_feed.log("position_limiter", "blocked",
                        {"symbol": asset.symbol, "strategy": strategy.name},
                        reasoning="Position limit reached")
                    continue

                # LLM agent analysis if available
                llm_approved = True
                llm_reasoning = ""
                if self._llm_provider:
                    llm_result = await self._run_llm_analysis(strategy, asset, prices, signals, "buy")
                    llm_approved = llm_result.get("approved", True)
                    llm_reasoning = llm_result.get("reasoning", "")
                    if not llm_approved:
                        activity_feed.log("decision_agent", "rejected",
                            {"symbol": asset.symbol, "strategy": strategy.name},
                            reasoning=llm_reasoning)
                        continue

                quote = await self._broker.quote(asset.symbol)
                price = quote.get("last", prices[-1])
                if price <= 0:
                    price = prices[-1]

                # Position sizing from strategy or default
                balance = await self._broker.balance()
                size_pct = strategy.optimal_position_size or settings.position_size_pct
                position_size = balance["cash"] * size_pct
                qty = int(position_size / price) if price > 0 else 0

                if qty > 0:
                    result = await self._broker.place_order(
                        symbol=asset.symbol, side="buy", qty=float(qty),
                        order_type="market", price=price,
                    )
                    if result.status == "filled":
                        self._record_trade(strategy.id, asset.id, "buy", qty, price, result)
                        self._trades_executed += 1
                        activity_feed.log("executor", "trade_executed",
                            {"symbol": asset.symbol, "side": "buy", "qty": qty, "price": price,
                             "strategy": strategy.name, "llm_reasoning": llm_reasoning})

                        # Log trade decision
                        self._log_trade_decision(strategy.id, asset.id, "buy", signals, llm_reasoning)

            elif signals.exits[-1]:
                positions = await self._broker.positions()
                for pos in positions:
                    if pos.get("symbol") == asset.symbol and pos.get("qty", 0) > 0:
                        quote = await self._broker.quote(asset.symbol)
                        price = quote.get("last", prices[-1])

                        # Position scaling — reduce losers
                        sell_qty = pos["qty"]
                        scaled = self._scale_position(pos, strategy)
                        if scaled and scaled.get("action") == "reduce":
                            sell_qty = max(1, int(pos["qty"] * scaled["scale_factor"]))

                        result = await self._broker.place_order(
                            symbol=asset.symbol, side="sell", qty=sell_qty,
                            order_type="market", price=price,
                        )
                        if result.status == "filled":
                            self._record_trade(strategy.id, asset.id, "sell", sell_qty, price, result)
                            self._trades_executed += 1
                            activity_feed.log("executor", "trade_executed",
                                {"symbol": asset.symbol, "side": "sell", "qty": sell_qty, "price": price,
                                 "strategy": strategy.name})

    async def _check_position_limits(self, symbol: str) -> bool:
        """Check position limits before opening new position."""
        try:
            from ..risk.position_limiter import PositionLimiter
            settings = get_settings()
            limiter = PositionLimiter(settings)
            positions = await self._broker.positions()
            result = limiter.can_open(positions, symbol)
            return result["allowed"]
        except Exception:
            return True

    async def _run_llm_analysis(self, strategy, asset, prices, signals, action) -> dict:
        """Run LLM signal + decision agent pipeline."""
        try:
            from ..agents.signal_agent import SignalAgent
            from ..agents.decision_agent import DecisionAgent
            from ..risk.manager import RiskManager

            signal_agent = SignalAgent(self._llm_provider, get_settings())
            signal_data = {
                "strategy": strategy.name, "symbol": asset.symbol,
                "action": action, "price": prices[-1],
                "rsi": None, "macd": None,
            }
            analysis = await signal_agent.analyze_signal(strategy.name, signal_data, {"prices": prices[-20:]})

            activity_feed.log("signal_agent", "analyzed",
                {"symbol": asset.symbol, "confidence": analysis.get("confidence", 0),
                 "action": analysis.get("action", "hold")},
                reasoning=analysis.get("reasoning", ""))

            if analysis.get("confidence", 0) < 0.3:
                return {"approved": False, "reasoning": f"Low confidence: {analysis.get('confidence', 0):.2f}"}

            risk_mgr = RiskManager()
            decision_agent = DecisionAgent(self._llm_provider, risk_mgr, get_settings())
            portfolio_state = {"positions": await self._broker.positions(), "balance": await self._broker.balance()}
            decision = await decision_agent.decide(analysis, portfolio_state)

            activity_feed.log("decision_agent", "decided",
                {"approved": decision.get("approved", False), "action": decision.get("final_action", "hold")},
                reasoning=decision.get("reasoning", ""))

            return decision
        except Exception as e:
            logger.debug(f"LLM analysis error: {e}")
            return {"approved": True, "reasoning": "LLM unavailable, proceeding with signal"}

    def _scale_position(self, position: dict, strategy: StrategyORM) -> dict | None:
        """Scale position based on performance."""
        try:
            from .position_scaler import PositionScaler
            scaler = PositionScaler()
            performance = {"win_rate": strategy.win_rate or 0, "unrealized_pnl": position.get("pnl", 0)}
            return scaler.scale_position(position, performance, get_settings())
        except Exception:
            return None

    def _log_trade_decision(self, strategy_id, asset_id, action, signals, reasoning):
        """Log trade decision to DB."""
        try:
            from .decision_log import TradeDecisionLog
            log = TradeDecisionLog()
            log.log_decision(
                signal={"entries": signals.entries[-5:], "exits": signals.exits[-5:]},
                reasoning=reasoning or "Signal-based entry",
                action=action, result="executed",
                strategy_id=strategy_id, asset_id=asset_id,
            )
        except Exception:
            pass

    async def _run_promotion_check(self) -> None:
        """Evaluate paper trading strategies for promotion/demotion."""
        try:
            from .promotion import PromotionManager
            settings = get_settings()
            pm = PromotionManager(settings)
            with get_db() as db:
                paper = db.query(StrategyORM).filter(
                    StrategyORM.status == StrategyStatus.PAPER_TRADING.value
                ).all()
                for s in paper:
                    trades = db.query(TradeORM).filter(TradeORM.strategy_id == s.id).all()
                    result = pm.evaluate(s, trades)
                    if result["eligible"]:
                        pm.promote(s.id, db)
                        activity_feed.log("promotion_manager", "promoted",
                            {"strategy_id": s.id, "strategy": s.name,
                             "win_rate": result["win_rate"], "trades": result["trade_count"]},
                            reasoning=f"Met all thresholds: wr={result['win_rate']:.2%}, trades={result['trade_count']}")
                        logger.info(f"Strategy {s.name} PROMOTED to live trading")
        except Exception as e:
            logger.debug(f"Promotion check error: {e}")

    async def _run_performance_review(self) -> None:
        """Monitor performance, run LLM review on underperformers, auto-adjust."""
        try:
            from ..risk.performance_monitor import PerformanceMonitor
            from ..risk.auto_adjuster import AutoAdjuster
            from ..risk.review_log import review_log
            settings = get_settings()
            monitor = PerformanceMonitor(settings)
            adjuster = AutoAdjuster()

            with get_db() as db:
                active = db.query(StrategyORM).filter(
                    StrategyORM.status.in_(["paper_trading", "promoted", "shortlisted"])
                ).all()

                for s in active:
                    trades = db.query(TradeORM).filter(TradeORM.strategy_id == s.id).all()
                    perf = monitor.analyze(s.id, trades, window_days=30)

                    if perf["underperforming"]:
                        activity_feed.log("performance_monitor", "flagged",
                            {"strategy": s.name, "flags": perf["flags"]},
                            reasoning=perf["recommendation"])

                        review_result = {"verdict": "adjust", "suggestions": perf["flags"],
                                         "parameter_changes": {}, "reasoning": perf["recommendation"]}

                        # LLM review if available
                        if self._llm_provider:
                            try:
                                from ..agents.review_agent import ReviewAgent
                                reviewer = ReviewAgent(self._llm_provider, settings)
                                review_result = await reviewer.review_strategy(
                                    {"name": s.name, "params": s.parameters}, perf,
                                    [{"side": t.side, "price": t.price, "quantity": t.quantity} for t in trades[-20:]]
                                )
                                activity_feed.log("review_agent", "reviewed",
                                    {"strategy": s.name, "verdict": review_result.get("verdict", "keep")},
                                    reasoning=review_result.get("reasoning", ""))
                            except Exception as e:
                                logger.debug(f"LLM review error: {e}")

                        # Auto-adjust parameters
                        before_params = json.loads(s.parameters) if s.parameters else {}
                        adjusted = adjuster.adjust(s.id, review_result, before_params)

                        if adjusted.get("changes_applied"):
                            s.parameters = json.dumps(adjusted["adjusted_params"])
                            db.flush()
                            review_log.log_review(
                                strategy_id=s.id, flagged_reason=str(perf["flags"]),
                                recommendation=review_result.get("verdict", "adjust"),
                                applied_changes=adjusted, before_params=before_params,
                                after_params=adjusted["adjusted_params"],
                            )
                            activity_feed.log("auto_adjuster", "adjusted",
                                {"strategy": s.name, "changes": adjusted["changes_applied"]})

        except Exception as e:
            logger.debug(f"Performance review error: {e}")

    async def _run_rotation(self) -> None:
        """Rotate strategies — demote underperformers, send back to research."""
        try:
            from ..risk.rotation import StrategyRotator
            from ..risk.performance_monitor import PerformanceMonitor
            settings = get_settings()
            rotator = StrategyRotator(settings)
            monitor = PerformanceMonitor(settings)

            with get_db() as db:
                active = db.query(StrategyORM).filter(
                    StrategyORM.status.in_(["paper_trading", "promoted", "shortlisted"])
                ).all()

                strategies_data = []
                perf_data = {}
                for s in active:
                    trades = db.query(TradeORM).filter(TradeORM.strategy_id == s.id).all()
                    perf = monitor.analyze(s.id, trades)
                    strategies_data.append({"id": s.id, "name": s.name, "status": s.status})
                    perf_data[s.id] = perf

                if not strategies_data:
                    return

                rotation = rotator.rotate(strategies_data, perf_data)

                for sid in rotation.get("demoted", []):
                    s = db.query(StrategyORM).filter(StrategyORM.id == sid).first()
                    if s:
                        s.status = StrategyStatus.DEMOTED.value
                        activity_feed.log("strategy_rotator", "demoted",
                            {"strategy": s.name, "reason": rotation["reasoning"].get(sid, "")})

                for sid in rotation.get("to_research", []):
                    s = db.query(StrategyORM).filter(StrategyORM.id == sid).first()
                    if s:
                        s.status = StrategyStatus.DISCOVERED.value
                        activity_feed.log("strategy_rotator", "sent_to_research",
                            {"strategy": s.name, "reason": "Re-tune parameters"})

                db.flush()

                if rotation["demoted"] or rotation["to_research"]:
                    logger.info(f"Rotation: {len(rotation['demoted'])} demoted, {len(rotation['to_research'])} to research")

        except Exception as e:
            logger.debug(f"Rotation error: {e}")

    def _record_trade(
        self, strategy_id: int, asset_id: int, side: str,
        qty: float, price: float, result: Any,
    ) -> None:
        with get_db() as db:
            trade = TradeORM(
                portfolio_id=self._portfolio_id,
                asset_id=asset_id,
                strategy_id=strategy_id,
                side=side,
                quantity=qty,
                price=price,
                commission=0.0,
                order_type="market",
                is_simulated=True,
                notes=f"order_id={result.order_id}",
            )
            db.add(trade)
            db.flush()


trading_executor = TradingExecutor()
