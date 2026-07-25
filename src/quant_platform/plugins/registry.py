"""Plugin registry — config-driven loading of broker, research, LLM adapters."""

from __future__ import annotations

from typing import Any

from .broker import BrokerAdapter
from .research import ResearchSource
from .llm import LLMProvider


class PluginRegistry:

    def __init__(self):
        self._brokers: dict[str, type[BrokerAdapter]] = {}
        self._research: dict[str, type[ResearchSource]] = {}
        self._llm: dict[str, type[LLMProvider]] = {}

    def register_broker(self, name: str, cls: type[BrokerAdapter]) -> None:
        self._brokers[name] = cls

    def register_research(self, name: str, cls: type[ResearchSource]) -> None:
        self._research[name] = cls

    def register_llm(self, name: str, cls: type[LLMProvider]) -> None:
        self._llm[name] = cls

    def get_broker(self, name: str, **kwargs: Any) -> BrokerAdapter:
        if name not in self._brokers:
            raise KeyError(f"Broker adapter '{name}' not registered. Available: {list(self._brokers.keys())}")
        return self._brokers[name](**kwargs)

    def get_research(self, name: str, **kwargs: Any) -> ResearchSource:
        if name not in self._research:
            raise KeyError(f"Research source '{name}' not registered. Available: {list(self._research.keys())}")
        return self._research[name](**kwargs)

    def get_llm(self, name: str, **kwargs: Any) -> LLMProvider:
        if name not in self._llm:
            raise KeyError(f"LLM provider '{name}' not registered. Available: {list(self._llm.keys())}")
        return self._llm[name](**kwargs)

    def list_brokers(self) -> list[str]:
        return list(self._brokers.keys())

    def list_research(self) -> list[str]:
        return list(self._research.keys())

    def list_llm(self) -> list[str]:
        return list(self._llm.keys())


registry = PluginRegistry()
