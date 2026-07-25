"""Base agent class for all specialized agents."""

from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

import anthropic

from ..config import Config
from ..models import AgentRole, Task, _now

logger = logging.getLogger(__name__)

LLM_MODEL = "claude-sonnet-4-6"
LLM_MAX_TOKENS = 16384


class BaseAgent(ABC):

    role: AgentRole
    system_prompt: str = ""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._dry_run = config.dry_run

    @property
    def name(self) -> str:
        return self.role.value

    @abstractmethod
    def execute(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's role on a task. Returns structured output."""

    @abstractmethod
    def dry_run_response(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        """Return a simulated response for dry-run validation."""

    def run(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        logger.info("[%s] Starting task: %s", self.name, task.title)
        start = time.monotonic()

        if self._dry_run:
            result = self.dry_run_response(task, context)
        else:
            result = self.execute(task, context)

        duration = time.monotonic() - start
        result["_meta"] = {
            "agent": self.name,
            "task_id": task.task_id,
            "duration_seconds": round(duration, 3),
            "timestamp": _now(),
            "dry_run": self._dry_run,
            "model": self.config.model,
        }
        logger.info("[%s] Completed task: %s (%.3fs)",
                     self.name, task.title, duration)
        return result

    def _call_llm(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.config.has_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set — cannot make LLM calls")

        client = anthropic.Anthropic(api_key=self.config.anthropic_api_key)
        try:
            response = client.messages.create(
                model=LLM_MODEL,
                max_tokens=LLM_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text

            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(raw)

            result["_llm_meta"] = {
                "model": response.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "stop_reason": response.stop_reason,
            }
            return result

        except anthropic.APIError as e:
            logger.error("[%s] Claude API error: %s", self.name, e)
            return {"error": f"API error: {e}", "action": "error"}
        except json.JSONDecodeError as e:
            logger.error("[%s] Failed to parse LLM JSON: %s\nRaw: %s",
                         self.name, e, raw[:500])
            return {"error": f"JSON parse error: {e}", "raw_response": raw[:2000],
                    "action": "error"}

    def _build_prompt(self, task: Task, context: dict[str, Any]) -> str:
        parts = [
            f"\nTask: {task.title}",
            f"Description: {task.description}",
            f"Phase: {task.phase_id}",
        ]
        if task.acceptance_criteria:
            parts.append("Acceptance Criteria:")
            for ac in task.acceptance_criteria:
                parts.append(f"  - {ac}")
        if context.get("phase_spec"):
            parts.append("\nPhase Specification:")
            parts.append(str(context["phase_spec"]))
        if context.get("knowledge"):
            parts.append("\nRelevant Knowledge:")
            parts.append(json.dumps(context["knowledge"], indent=2))
        if context.get("previous_output"):
            parts.append("\nPrevious Agent Output:")
            parts.append(json.dumps(context["previous_output"], indent=2))
        if context.get("review_findings"):
            parts.append("\nReview Findings to Address:")
            parts.append(json.dumps(context["review_findings"], indent=2))
        if context.get("artifact_contents"):
            parts.append("\nArtifact Contents for Review:")
            for path, content in context["artifact_contents"].items():
                parts.append(f"\n--- {path} ---")
                parts.append(content)
        return "\n".join(parts)
