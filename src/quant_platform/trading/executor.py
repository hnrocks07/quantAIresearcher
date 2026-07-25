"""Trading executor — runs shortlisted strategies in paper/live mode with kill switch guard."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..database import get_db
from ..models import (
    StrategyORM, AssetORM, OHLCVORM, PortfolioORM, PositionORM, TradeORM,
    StrategyStatus, PositionStatus,
)
from ..plugins.broker import BrokerAdapter, FeeSchedule
from ..kill_switch import kill_switch
from ..event_bus import event_bus
from ..logging import get_logger
from ..research.strategies import BUILTIN_STRATEGIES

logger = get_logger("trading_executor")


class ExecutorStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    KILLED = "killed"


class TradingExecutor:

    def __init__(self):
        self._status = ExecutorStatus.IDLE
        self._broker: BrokerAdapter | None = None
        self._portfolio_id: int | None = None
        self._trades_executed: int = 0
        self._stop_requested: bool = False
        self._task: asyncio.Task | None = None
        self._cycle_count: int = 0

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

    async def _run_loop(self, interval: int) -> None:
        try:
            while not self._stop_requested:
                try:
                    kill_switch.check_or_raise()
                except RuntimeError:
                    self._status = ExecutorStatus.KILLED
                    logger.warning("Kill switch active — executor halted")
                    await event_bus.emit("trading.killed", "executor")
                    return

                await self._execute_cycle()
                self._cycle_count += 1

                await asyncio.sleep(interval)

            self._status = ExecutorStatus.STOPPED
            logger.info("Executor stopped")

        except Exception as e:
            logger.error(f"Executor error: {e}")
            self._status = ExecutorStatus.STOPPED

    async def _execute_cycle(self) -> None:
        with get_db() as db:
            shortlisted = db.query(StrategyORM).filter(
                StrategyORM.status.in_([
                    StrategyStatus.SHORTLISTED.value,
                    StrategyStatus.PAPER_TRADING.value,
                ])
            ).all()

        for strategy in shortlisted:
            try:
                await self._execute_strategy(strategy)
            except Exception as e:
                logger.warning(f"Strategy {strategy.name} execution error: {e}")

    async def _execute_strategy(self, strategy: StrategyORM) -> None:
        params = json.loads(strategy.parameters) if strategy.parameters else {}
        base_name = strategy.name.split("_")[0] + "_" + strategy.name.split("_")[1] if "_" in strategy.name else strategy.name

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
                quote = await self._broker.quote(asset.symbol)
                price = quote.get("last", prices[-1])
                if price <= 0:
                    price = prices[-1]

                balance = await self._broker.balance()
                position_size = balance["cash"] * 0.02
                qty = int(position_size / price) if price > 0 else 0

                if qty > 0:
                    result = await self._broker.place_order(
                        symbol=asset.symbol,
                        side="buy",
                        qty=float(qty),
                        order_type="market",
                        price=price,
                    )
                    if result.status == "filled":
                        self._record_trade(strategy.id, asset.id, "buy", qty, price, result)
                        self._trades_executed += 1

            elif signals.exits[-1]:
                positions = await self._broker.positions()
                for pos in positions:
                    if pos.get("symbol") == asset.symbol and pos.get("qty", 0) > 0:
                        quote = await self._broker.quote(asset.symbol)
                        price = quote.get("last", prices[-1])
                        result = await self._broker.place_order(
                            symbol=asset.symbol,
                            side="sell",
                            qty=pos["qty"],
                            order_type="market",
                            price=price,
                        )
                        if result.status == "filled":
                            self._record_trade(strategy.id, asset.id, "sell", pos["qty"], price, result)
                            self._trades_executed += 1

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
