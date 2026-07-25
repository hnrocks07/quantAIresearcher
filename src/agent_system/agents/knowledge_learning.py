"""Knowledge Learning Agent - captures lessons and reusable skills."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import AgentRole, Task, KnowledgeEntry, _uid
from .base import BaseAgent


class KnowledgeLearningAgent(BaseAgent):

    role = AgentRole.KNOWLEDGE_LEARNING
    system_prompt = (
        "You are the Knowledge Learning Agent. Capture decisions, research, "
        "failures/fixes, patterns, pitfalls, retrospectives, and reusable "
        "skills. Maintain the SKILLS_INDEX. Track knowledge retrieval/reuse "
        "events so later phases can demonstrate whether accumulated lessons "
        "improved delivery. Do not claim learning without traceable evidence."
    )

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def execute(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(task, context)
        prompt += (
            "\n\nRespond with ONLY a JSON object (no markdown, no explanation) "
            "with these fields:\n"
            '- "action": "learn"\n'
            '- "entries": list of knowledge entry objects, each with:\n'
            '  - "entry_id": unique string\n'
            '  - "category": "pattern", "decision", "failure_lesson", '
            '"review_insight", "architecture", or "best_practice"\n'
            '  - "title": concise title of what was learned\n'
            '  - "content": detailed content of the knowledge entry\n'
            f'  - "tags": list of tag strings (include "{task.phase_id}")\n'
            f'  - "source_agent": "{self.name}"\n'
            '- "knowledge_stored": number of entries\n'
            '- "skills_index_updated": true\n'
        )
        return self._call_llm(self.system_prompt, prompt)

    def dry_run_response(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        entries = [
            {
                "entry_id": _uid(),
                "category": "pattern",
                "title": f"Pattern learned from: {task.title}",
                "content": "[DRY-RUN] Captured implementation pattern",
                "tags": ["dry-run", task.phase_id],
                "source_agent": self.name,
            }
        ]

        failures = context.get("failures", [])
        if failures:
            entries.append({
                "entry_id": _uid(),
                "category": "failure_lesson",
                "title": f"Failure lesson from: {task.title}",
                "content": "[DRY-RUN] What failed, why, and how it was fixed",
                "tags": ["failure", "lesson", task.phase_id],
                "source_agent": self.name,
            })

        review_findings = context.get("review_findings", [])
        if review_findings:
            entries.append({
                "entry_id": _uid(),
                "category": "review_insight",
                "title": f"Review insights from: {task.title}",
                "content": "[DRY-RUN] Patterns from review findings",
                "tags": ["review", "quality", task.phase_id],
                "source_agent": self.name,
            })

        return {
            "action": "learn",
            "entries": entries,
            "knowledge_stored": len(entries),
            "skills_index_updated": True,
            "retrieval_events": context.get("knowledge_retrieval_count", 0),
            "reuse_evidence": bool(context.get("knowledge")),
        }
