"""LLMProvider abstract interface — swap LLM backends via config."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    metadata: dict[str, Any] | None = None


class LLMProvider(ABC):

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0, max_tokens: int = 4096) -> LLMResponse: ...

    @abstractmethod
    async def generate_json(self, prompt: str, system: str | None = None, temperature: float = 0.0, max_tokens: int = 4096) -> dict[str, Any]: ...
