"""Review transparency log — full audit trail of strategy reviews."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class ReviewTransparencyLog:

    def __init__(self):
        self._log: list[dict[str, Any]] = []

    def log_review(
        self,
        strategy_id: int,
        flagged_reason: str,
        recommendation: str,
        applied_changes: dict,
        before_params: dict,
        after_params: dict,
    ) -> None:
        self._log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "strategy_id": strategy_id,
            "flagged_reason": flagged_reason,
            "recommendation": recommendation,
            "applied_changes": applied_changes,
            "before_params": before_params,
            "after_params": after_params,
        })

    def get_log(self, limit: int = 100, strategy_id: int | None = None) -> list[dict[str, Any]]:
        entries = self._log
        if strategy_id is not None:
            entries = [e for e in entries if e["strategy_id"] == strategy_id]
        return entries[-limit:]

    def clear(self) -> None:
        self._log.clear()


review_log = ReviewTransparencyLog()
