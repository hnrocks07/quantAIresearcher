"""Position limiter — enforces max position counts."""

from __future__ import annotations

from typing import Any

from ..config import Settings


class PositionLimiter:

    def __init__(self, settings: Settings):
        self._settings = settings

    def can_open(self, current_positions: list, instrument: str) -> dict[str, Any]:
        total = len(current_positions)
        instrument_count = sum(1 for p in current_positions if p.get("instrument") == instrument)

        reasons: list[str] = []
        if total >= self._settings.max_positions:
            reasons.append(f"Total positions {total} >= max {self._settings.max_positions}")
        if instrument_count >= self._settings.max_position_per_instrument:
            reasons.append(f"Instrument positions {instrument_count} >= max {self._settings.max_position_per_instrument}")

        return {
            "allowed": len(reasons) == 0,
            "total_positions": total,
            "instrument_positions": instrument_count,
            "reasons": reasons,
        }
