"""Agent activity feed — in-memory log of all agent actions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class AgentActivityFeed:

    def __init__(self):
        self._feed: list[dict[str, Any]] = []

    def log(self, agent_name: str, action: str, details: dict, reasoning: str = "") -> None:
        self._feed.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_name": agent_name,
            "action": action,
            "details": details,
            "reasoning": reasoning,
        })

    def get_feed(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._feed[-limit:]

    def get_by_agent(self, agent_name: str, limit: int = 50) -> list[dict[str, Any]]:
        filtered = [e for e in self._feed if e["agent_name"] == agent_name]
        return filtered[-limit:]

    def clear(self) -> None:
        self._feed.clear()


activity_feed = AgentActivityFeed()
