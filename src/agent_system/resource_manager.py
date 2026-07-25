"""Resource and concurrency guardrails for MacBook Air M3/16GB."""

from __future__ import annotations

import logging
import threading
from typing import Any

from .config import Config

logger = logging.getLogger(__name__)


class ResourceManager:

    def __init__(self, config: Config) -> None:
        self.config = config
        self._semaphore = threading.Semaphore(config.max_concurrent_agents)
        self._active_agents: list[str] = []
        self._lock = threading.Lock()

    def acquire(self, agent_name: str) -> bool:
        acquired = self._semaphore.acquire(blocking=False)
        if acquired:
            with self._lock:
                self._active_agents.append(agent_name)
            logger.info("Agent slot acquired: %s (active: %d/%d)",
                         agent_name, len(self._active_agents),
                         self.config.max_concurrent_agents)
        else:
            logger.warning("Agent slot denied: %s (at max: %d)",
                            agent_name, self.config.max_concurrent_agents)
        return acquired

    def release(self, agent_name: str) -> None:
        with self._lock:
            if agent_name in self._active_agents:
                self._active_agents.remove(agent_name)
        self._semaphore.release()
        logger.info("Agent slot released: %s", agent_name)

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active_agents)

    @property
    def available_slots(self) -> int:
        return self.config.max_concurrent_agents - self.active_count

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "max_concurrent_agents": self.config.max_concurrent_agents,
                "active_agents": list(self._active_agents),
                "active_count": len(self._active_agents),
                "available_slots": (self.config.max_concurrent_agents
                                     - len(self._active_agents)),
            }

    def check_constraints(self) -> dict[str, Any]:
        return {
            "concurrent_agents_ok": self.active_count < self.config.max_concurrent_agents,
            "status": self.get_status(),
            "hardware_target": "MacBook Air M3, 8 cores, 16GB",
            "notes": [
                "Max 2 concurrent LLM agents",
                "Backtest workers limited to 3",
                "Optimization workers limited to 2",
                "Heavy jobs queued/throttled",
            ],
        }
