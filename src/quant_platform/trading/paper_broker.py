"""Paper trading broker — simulates order execution with fee tracking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..plugins.broker import BrokerAdapter, FeeSchedule, OrderResult
from ..logging import get_logger

logger = get_logger("paper_broker")


class PaperBroker(BrokerAdapter):

    def __init__(self, initial_balance: float = 1000000.0, fee_schedule: FeeSchedule | None = None):
        self._balance = initial_balance
        self._initial_balance = initial_balance
        self._fee_schedule = fee_schedule or FeeSchedule()
        self._positions: dict[str, dict[str, Any]] = {}
        self._orders: dict[str, dict[str, Any]] = {}
        self._prices: dict[str, float] = {}
        self._connected = False

    def name(self) -> str:
        return "paper"

    def fee_schedule(self) -> FeeSchedule:
        return self._fee_schedule

    async def connect(self) -> None:
        self._connected = True
        logger.info("Paper broker connected")

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Paper broker disconnected")

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price

    async def place_order(
        self, symbol: str, side: str, qty: float,
        order_type: str, price: float | None = None,
    ) -> OrderResult:
        exec_price = price or self._prices.get(symbol, 0.0)
        if exec_price <= 0:
            return OrderResult(order_id="", status="rejected", message=f"No price for {symbol}")

        trade_value = exec_price * qty
        fees = self._fee_schedule.calculate_total_fees(trade_value, side)
        total_cost = trade_value + fees if side in ("buy", "long") else -trade_value + fees

        if side in ("buy", "long") and (trade_value + fees) > self._balance:
            return OrderResult(order_id="", status="rejected", message="Insufficient balance")

        order_id = str(uuid.uuid4())[:8]

        if side in ("buy", "long"):
            self._balance -= trade_value + fees
            pos = self._positions.get(symbol, {"qty": 0.0, "avg_price": 0.0, "side": "long"})
            total_qty = pos["qty"] + qty
            if total_qty > 0:
                pos["avg_price"] = (pos["avg_price"] * pos["qty"] + exec_price * qty) / total_qty
            pos["qty"] = total_qty
            pos["side"] = "long"
            self._positions[symbol] = pos
        else:
            self._balance += trade_value - fees
            pos = self._positions.get(symbol)
            if pos:
                pos["qty"] -= qty
                if pos["qty"] <= 0:
                    del self._positions[symbol]

        self._orders[order_id] = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": exec_price,
            "fees": fees,
            "status": "filled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Paper order: {side} {qty} {symbol} @ {exec_price} (fees: {fees:.2f})")

        return OrderResult(
            order_id=order_id,
            status="filled",
            filled_qty=qty,
            filled_price=exec_price,
        )

    async def cancel_order(self, order_id: str) -> bool:
        return order_id in self._orders

    async def order_status(self, order_id: str) -> dict[str, Any]:
        return self._orders.get(order_id, {"status": "unknown"})

    async def positions(self) -> list[dict[str, Any]]:
        return [
            {"symbol": sym, **pos}
            for sym, pos in self._positions.items()
        ]

    async def balance(self) -> dict[str, float]:
        position_value = sum(
            pos["qty"] * self._prices.get(sym, pos["avg_price"])
            for sym, pos in self._positions.items()
        )
        return {
            "cash": round(self._balance, 2),
            "positions_value": round(position_value, 2),
            "total_equity": round(self._balance + position_value, 2),
            "initial_balance": self._initial_balance,
            "pnl": round(self._balance + position_value - self._initial_balance, 2),
        }

    async def quote(self, symbol: str) -> dict[str, float]:
        price = self._prices.get(symbol, 0.0)
        return {"bid": price, "ask": price, "last": price}
