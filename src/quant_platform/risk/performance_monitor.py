"""Performance monitor — analyzes strategy trading performance over a window."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from ..config import Settings
from ..models import TradeORM


class PerformanceMonitor:

    def __init__(self, settings: Settings):
        self._settings = settings

    def analyze(self, strategy_id: int, trades: list[TradeORM], window_days: int = 30) -> dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        recent = [t for t in trades if t.executed_at and t.executed_at.replace(
            tzinfo=timezone.utc if t.executed_at.tzinfo is None else t.executed_at.tzinfo
        ) >= cutoff]

        if not recent:
            return {
                "metrics": {"win_rate": 0, "avg_pnl": 0, "max_drawdown": 0, "sharpe": 0},
                "underperforming": True,
                "flags": ["No recent trades"],
                "recommendation": "monitor",
            }

        pnls = []
        for t in recent:
            multiplier = 1.0 if t.side == "sell" else -1.0
            pnls.append(multiplier * t.quantity * t.price)

        wins = sum(1 for p in pnls if p > 0)
        win_rate = wins / len(pnls) if pnls else 0

        avg_pnl = float(np.mean(pnls)) if pnls else 0
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_drawdown = float(np.max(drawdowns)) / max(float(np.max(running_max)), 1.0) if len(drawdowns) > 0 else 0

        std = float(np.std(pnls)) if len(pnls) > 1 else 1.0
        sharpe = (avg_pnl / std) if std > 0 else 0.0

        flags: list[str] = []
        if win_rate < 0.4:
            flags.append(f"Low win rate: {win_rate:.2%}")
        if max_drawdown > 0.15:
            flags.append(f"High drawdown: {max_drawdown:.2%}")
        if sharpe < 0:
            flags.append(f"Negative Sharpe: {sharpe:.2f}")

        underperforming = len(flags) > 0

        if underperforming:
            recommendation = "review"
        else:
            recommendation = "continue"

        return {
            "metrics": {
                "win_rate": round(win_rate, 4),
                "avg_pnl": round(avg_pnl, 2),
                "max_drawdown": round(max_drawdown, 4),
                "sharpe": round(sharpe, 4),
            },
            "underperforming": underperforming,
            "flags": flags,
            "recommendation": recommendation,
        }
