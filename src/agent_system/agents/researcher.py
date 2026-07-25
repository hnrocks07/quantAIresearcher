"""Research Agent - resolves uncertainty with authoritative sources."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import AgentRole, Task
from .base import BaseAgent


class ResearchAgent(BaseAgent):

    role = AgentRole.RESEARCHER
    system_prompt = (
        "You are the Researcher. Resolve uncertainty using authoritative "
        "sources. For TradingView/Pine, verify authorized mechanisms, "
        "API/source limitations, licensing, and semantics. Never recommend "
        "bypassing controls. Store findings locally. Preserve research "
        "provenance and link artifacts to requesting phase/task/run."
    )

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def execute(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(task, context)
        prompt += (
            "\n\nRespond with ONLY a JSON object (no markdown, no explanation) "
            "with these fields:\n"
            '- "action": "research"\n'
            '- "findings": list of objects, each with:\n'
            '  - "topic": what was researched\n'
            '  - "source": source type (e.g. "documentation", "best_practices")\n'
            '  - "summary": detailed research finding\n'
            '  - "confidence": "high", "medium", or "low"\n'
            '  - "provenance": {"phase_id": string, "task_id": string}\n'
            '  - "licensing_check": "oss_compatible" or "not_applicable"\n'
            '  - "access_controls_respected": true\n'
            '- "research_questions_resolved": number of questions resolved\n'
            '- "follow_up_questions": list of remaining questions (empty if all resolved)\n'
        )
        return self._call_llm(self.system_prompt, prompt)

    def dry_run_response(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "action": "research",
            "findings": [
                {
                    "topic": f"Research for: {task.title}",
                    "source": "authoritative_documentation",
                    "summary": "[DRY-RUN] Research finding simulated",
                    "confidence": "high",
                    "provenance": {
                        "phase_id": task.phase_id,
                        "task_id": task.task_id,
                        "timestamp": "simulated",
                    },
                    "licensing_check": "not_applicable",
                    "access_controls_respected": True,
                }
            ],
            "research_questions_resolved": 1,
            "follow_up_questions": [],
        }
