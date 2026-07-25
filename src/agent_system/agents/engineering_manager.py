"""Engineering Manager Agent - owns roadmap, delegation, acceptance."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import AgentRole, Task
from .base import BaseAgent


class EngineeringManagerAgent(BaseAgent):

    role = AgentRole.ENGINEERING_MANAGER
    system_prompt = (
        "You are the Engineering Manager. You own the roadmap, dependencies, "
        "delegation, acceptance criteria, review/remediation workflow, "
        "persistent state, resource management, and knowledge capture. "
        "Enforce greenfield/local-first scope. Enforce evidence capture for "
        "every phase/task/agent handoff. Track human intervention explicitly. "
        "Never optimize metrics by hiding failures."
    )

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def execute(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(task, context)
        prompt += (
            "\n\nRespond with ONLY a JSON object (no markdown, no explanation) "
            "with these fields:\n"
            '- "action": "delegate"\n'
            '- "decision": string describing your evaluation\n'
            '- "assessment": string with task complexity/risk assessment\n'
            '- "delegation_plan": list of objects with "agent" and "action" keys '
            '(use agent names: PlannerAgent, ResearchAgent, SeniorEngineerAgent, ReviewerAgent)\n'
            '- "acceptance_criteria_verified": boolean\n'
            '- "resource_check": {"concurrent_agents": number, "within_limits": boolean}\n'
            '- "evidence_hooks": {"run_id_tracking": true, "phase_id_tracking": true, '
            '"task_id_tracking": true, "handoff_logging": true, "human_intervention_logging": true}\n'
        )
        return self._call_llm(self.system_prompt, prompt)

    def dry_run_response(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "action": "delegate",
            "decision": f"[DRY-RUN] Phase {task.phase_id} task '{task.title}' "
                         "evaluated and ready for delegation",
            "delegation_plan": [
                {"agent": "PlannerAgent", "action": "decompose"},
                {"agent": "SeniorEngineerAgent", "action": "implement"},
                {"agent": "ReviewerAgent", "action": "review"},
            ],
            "acceptance_criteria_verified": True,
            "resource_check": {
                "concurrent_agents": 1,
                "max_allowed": self.config.max_concurrent_agents,
                "within_limits": True,
            },
            "evidence_hooks": {
                "run_id_tracking": True,
                "phase_id_tracking": True,
                "task_id_tracking": True,
                "handoff_logging": True,
                "human_intervention_logging": True,
            },
        }
