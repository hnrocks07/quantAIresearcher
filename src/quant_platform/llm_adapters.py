"""Concrete LLM adapters — Claude (via LiteLLM) and Ollama."""

from __future__ import annotations

import json
from typing import Any

from .plugins.llm import LLMProvider, LLMResponse


class ClaudeAdapter(LLMProvider):

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None, base_url: str | None = None):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url

    def name(self) -> str:
        return "claude"

    async def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0, max_tokens: int = 4096) -> LLMResponse:
        import litellm
        messages = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["api_base"] = self._base_url
        if system:
            kwargs["messages"] = [{"role": "system", "content": system}] + messages

        response = await litellm.acompletion(**kwargs)
        return LLMResponse(
            content=response.choices[0].message.content,
            model=self._model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

    async def generate_json(self, prompt: str, system: str | None = None, temperature: float = 0.0, max_tokens: int = 4096) -> dict[str, Any]:
        json_system = (system or "") + "\nRespond ONLY with valid JSON, no markdown, no explanation."
        resp = await self.generate(prompt, system=json_system, temperature=temperature, max_tokens=max_tokens)
        text = resp.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)


class OllamaAdapter(LLMProvider):

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434"):
        self._model = model
        self._base_url = base_url

    def name(self) -> str:
        return "ollama"

    async def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0, max_tokens: int = 4096) -> LLMResponse:
        import litellm
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages = [{"role": "system", "content": system}] + messages

        response = await litellm.acompletion(
            model=f"ollama/{self._model}",
            messages=messages,
            api_base=self._base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            model=self._model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

    async def generate_json(self, prompt: str, system: str | None = None, temperature: float = 0.0, max_tokens: int = 4096) -> dict[str, Any]:
        json_system = (system or "") + "\nRespond ONLY with valid JSON, no markdown, no explanation."
        resp = await self.generate(prompt, system=json_system, temperature=temperature, max_tokens=max_tokens)
        text = resp.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
