"""Kill switch service — checks state before every trading action."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from .event_bus import event_bus
from .logging import get_logger, audit

logger = get_logger("kill_switch")


class KillSwitch:

    def __init__(self):
        self._active: bool = False
        self._triggered_by: str | None = None
        self._triggered_at: datetime | None = None
        self._reason: str | None = None
        self._last_heartbeat: float = time.monotonic()
        self._heartbeat_timeout: int = 15
        self._history: list[dict[str, Any]] = []

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_safe_to_trade(self) -> bool:
        if self._active:
            return False
        elapsed = time.monotonic() - self._last_heartbeat
        if elapsed > self._heartbeat_timeout:
            logger.warning(f"Heartbeat timeout ({elapsed:.0f}s > {self._heartbeat_timeout}s), blocking trades")
            return False
        return True

    async def trigger(self, source: str, reason: str) -> None:
        self._active = True
        self._triggered_by = source
        self._triggered_at = datetime.now(timezone.utc)
        self._reason = reason
        self._history.append({
            "action": "triggered",
            "source": source,
            "reason": reason,
            "timestamp": self._triggered_at.isoformat(),
        })
        audit.log("kill_switch_triggered", source, {"reason": reason})
        await event_bus.emit("kill_switch.triggered", source, reason=reason)
        logger.critical(f"KILL SWITCH TRIGGERED by {source}: {reason}")

    async def reset(self, source: str) -> None:
        self._active = False
        self._triggered_by = None
        self._triggered_at = None
        self._reason = None
        self._last_heartbeat = time.monotonic()
        self._history.append({
            "action": "reset",
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        audit.log("kill_switch_reset", source)
        await event_bus.emit("kill_switch.reset", source)
        logger.info(f"Kill switch reset by {source}")

    def heartbeat(self) -> None:
        self._last_heartbeat = time.monotonic()

    def check_or_raise(self, action: str) -> None:
        if not self.is_safe_to_trade:
            raise RuntimeError(f"Kill switch active — cannot execute: {action}")

    def status(self) -> dict[str, Any]:
        elapsed = time.monotonic() - self._last_heartbeat
        return {
            "is_active": self._active,
            "is_safe_to_trade": self.is_safe_to_trade,
            "triggered_by": self._triggered_by,
            "triggered_at": self._triggered_at.isoformat() if self._triggered_at else None,
            "reason": self._reason,
            "heartbeat_age_seconds": round(elapsed, 1),
            "heartbeat_timeout": self._heartbeat_timeout,
            "history": self._history[-20:],
        }


kill_switch = KillSwitch()
