"""Activity event bus — pub/sub for all system events, dashboard consumption ready."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Awaitable

from .logging import get_logger

logger = get_logger("event_bus")


@dataclass
class Event:
    event_type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._all_handlers: list[EventHandler] = []
        self._history: list[Event] = []
        self._max_history: int = 10000

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        self._all_handlers.append(handler)

    async def publish(self, event: Event) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        handlers = self._handlers.get(event.event_type, []) + self._all_handlers
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.event_type}: {e}")

    async def emit(self, event_type: str, source: str, **payload: Any) -> None:
        await self.publish(Event(event_type=event_type, source=source, payload=payload))

    def recent(self, limit: int = 100, event_type: str | None = None) -> list[Event]:
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def clear(self) -> None:
        self._handlers.clear()
        self._all_handlers.clear()
        self._history.clear()


event_bus = EventBus()
