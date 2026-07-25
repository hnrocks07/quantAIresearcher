"""ResearchSource abstract interface — swap research providers via config."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ImportedStrategy:
    name: str
    source: str
    source_ref: str
    description: str = ""
    parameters: dict[str, Any] | None = None
    pine_script: str | None = None
    license: str = "unknown"


class ResearchSource(ABC):

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def discover_strategies(self, limit: int = 50) -> list[ImportedStrategy]: ...

    @abstractmethod
    async def get_strategy_details(self, source_ref: str) -> ImportedStrategy | None: ...

    @abstractmethod
    async def get_alerts(self) -> list[dict[str, Any]]: ...
