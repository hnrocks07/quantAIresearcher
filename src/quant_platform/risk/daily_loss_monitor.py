"""Daily loss monitor — triggers kill switch when loss cap breached."""

from __future__ import annotations

from typing import Any

from ..config import Settings
from ..kill_switch import KillSwitch
from ..models import TradeORM


class DailyLossMonitor:

    def __init__(self, settings: Settings, kill_switch: KillSwitch):
        self._settings = settings
        self._kill_switch = kill_switch

    async def check(self, trades_today: list[TradeORM], starting_capital: float) -> dict[str, Any]:
        pnl_today = 0.0
        for t in trades_today:
            multiplier = 1.0 if t.side == "sell" else -1.0
            pnl_today += multiplier * t.quantity * t.price

        loss_pct = abs(pnl_today / starting_capital) if starting_capital > 0 and pnl_today < 0 else 0.0
        cap_pct = self._settings.daily_loss_cap_pct
        breached = pnl_today < 0 and loss_pct >= cap_pct

        if breached:
            await self._kill_switch.trigger("daily_loss_monitor", "daily_loss_cap_exceeded")

        return {
            "pnl_today": round(pnl_today, 2),
            "loss_pct": round(loss_pct, 4),
            "cap_pct": cap_pct,
            "breached": breached,
        }
