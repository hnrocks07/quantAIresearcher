"""Position scaler — adjusts position sizes based on performance."""

from __future__ import annotations

from typing import Any

from ..config import Settings


class PositionScaler:

    def scale_position(self, position: dict, performance: dict, settings: Settings) -> dict[str, Any]:
        current_size = position.get("size", 0.0)
        unrealized_pnl = position.get("unrealized_pnl", 0.0)
        win_rate = performance.get("win_rate", 0.5)
        loss_pct = performance.get("loss_pct", 0.0)

        if unrealized_pnl > 0 and win_rate > 0.6:
            scale_factor = min(1.5, 1 + win_rate - 0.5)
            action = "add"
        elif unrealized_pnl < 0:
            scale_factor = max(0.5, 1 - abs(loss_pct))
            action = "reduce"
        else:
            scale_factor = 1.0
            action = "hold"

        suggested_size = current_size * scale_factor

        return {
            "current_size": current_size,
            "suggested_size": round(suggested_size, 4),
            "scale_factor": round(scale_factor, 4),
            "action": action,
            "reasoning": f"Win rate {win_rate:.2%}, PnL {unrealized_pnl:.2f} -> {action} (factor {scale_factor:.2f})",
        }
