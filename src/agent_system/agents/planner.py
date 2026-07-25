"""Planner Agent - decomposes phases into testable tasks."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import AgentRole, Task, _uid
from .base import BaseAgent


class PlannerAgent(BaseAgent):

    role = AgentRole.PLANNER
    system_prompt = (
        "You are the Planner. Decompose phases into small, testable tasks "
        "with dependencies, acceptance criteria, DB/data impact assessment, "
        "required tests, risks, resource needs, and research questions. "
        "Include measurable outcomes and evidence/telemetry requirements. "
        "Do not implement."
    )

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def execute(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(task, context)
        prompt += (
            "\n\nRespond with ONLY a JSON object (no markdown, no explanation) "
            "with these fields:\n"
            '- "action": "plan"\n'
            f'- "phase_id": "{task.phase_id}"\n'
            '- "tasks": list of task objects, each with:\n'
            '  - "task_id": unique string ID (use format "T-001", "T-002", etc.)\n'
            '  - "title": concise task title\n'
            '  - "description": detailed description of what to do\n'
            '  - "acceptance_criteria": list of measurable criteria strings\n'
            '  - "dependencies": list of task_id strings this depends on (empty list if none)\n'
            '  - "estimated_effort": "low", "medium", or "high"\n'
            '  - "risks": list of risk strings\n'
            '  - "research_needed": boolean\n'
            '  - "tests_required": list of test name strings\n'
            '  - "evidence_requirements": list of what evidence to capture\n'
            '- "total_tasks": number of tasks\n'
            '- "research_questions": list of open questions needing research\n'
            '- "resource_estimate": {"estimated_duration": string, "concurrent_agents_needed": number}\n'
        )
        return self._call_llm(self.system_prompt, prompt)

    def dry_run_response(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        sub_tasks = []
        for i, step in enumerate([
            ("Design", "Design the component architecture"),
            ("Implement", "Implement core functionality with tests"),
            ("Test", "Write and run comprehensive tests"),
        ], 1):
            sub_tasks.append({
                "task_id": _uid(),
                "title": f"{step[0]}: {task.title}",
                "description": step[1],
                "acceptance_criteria": [
                    f"Acceptance criterion {i}.1: Component passes unit tests",
                    f"Acceptance criterion {i}.2: Meets resource constraints",
                ],
                "dependencies": [] if i == 1 else [sub_tasks[-1]["task_id"]],
                "estimated_effort": "medium",
                "risks": ["Scope creep", "Resource constraint on M3"],
                "research_needed": i == 1,
                "tests_required": [
                    f"test_{task.title.lower().replace(' ', '_')}_{i}"
                ],
                "evidence_requirements": [
                    "Capture start/end timestamps",
                    "Record artifacts produced",
                    "Log test execution results",
                ],
            })
        return {
            "action": "plan",
            "phase_id": task.phase_id,
            "tasks": sub_tasks,
            "total_tasks": len(sub_tasks),
            "research_questions": [
                "Are there existing patterns to reuse from knowledge base?"
            ],
            "resource_estimate": {
                "estimated_duration": "medium",
                "concurrent_agents_needed": 1,
            },
        }
