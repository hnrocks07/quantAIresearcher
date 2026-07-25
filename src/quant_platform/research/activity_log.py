"""Research activity log — in-memory audit trail."""

from __future__ import annotations

from datetime import datetime, timezone


class ResearchActivityLog:

    def __init__(self):
        self._entries: list[dict] = []

    def log_action(
        self,
        action: str,
        strategy: str,
        details: str = "",
        reasoning: str = "",
    ) -> None:
        self._entries.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "strategy": strategy,
            "details": details,
            "reasoning": reasoning,
        })

    def get_log(self, limit: int = 100) -> list[dict]:
        return self._entries[-limit:]

    def clear(self) -> None:
        self._entries.clear()


activity_log = ResearchActivityLog()
