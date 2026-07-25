"""Senior Engineer Agent - implements with tests, migrations, docs."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import AgentRole, Task
from .base import BaseAgent


class SeniorEngineerAgent(BaseAgent):

    role = AgentRole.SENIOR_ENGINEER
    system_prompt = (
        "You are the Senior Engineer. Implement incrementally with tests, "
        "migrations, and documentation. Read decisions and lessons first. "
        "Keep data local by default, secrets out of source/logs, generated "
        "code sandboxed, resources bounded, real trading disabled. "
        "Never self-approve. Link implementation/test artifacts to "
        "task/run identifiers."
    )

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def execute(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(task, context)
        is_remediation = bool(context.get("review_findings"))
        action = "remediate" if is_remediation else "implement"
        prompt += (
            "\n\nIMPORTANT: Keep your response concise to avoid truncation. "
            "For file_contents, write focused content — avoid excessive boilerplate.\n\n"
            "Respond with ONLY a JSON object (no markdown, no explanation) "
            "with these fields:\n"
            f'- "action": "{action}"\n'
            '- "artifacts": list of relative file paths created/modified\n'
            '- "file_contents": object mapping relative file path to full file content string '
            '(the orchestrator will write these files to disk). '
            'Keep each file focused and concise. Use \\n for newlines within strings.\n'
            '- "tests_written": list of objects with "name", "status" ("PASSED"), "type" ("unit")\n'
            '- "tests_passed": boolean (true if all tests conceptually pass)\n'
            '- "implementation_notes": string describing what was done\n'
            '- "secrets_in_code": false (MUST be false — no secrets in code)\n'
            '- "resource_bounded": true (MUST be true)\n'
            '- "real_trading_disabled": true (MUST be true — no real money trading)\n'
        )
        if is_remediation:
            prompt += (
                '- "remediation_applied": true\n'
                '- "findings_addressed": list of finding_id strings that were fixed\n'
            )
        return self._call_llm(self.system_prompt, prompt)

    def dry_run_response(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        is_remediation = bool(context.get("review_findings"))
        return {
            "action": "remediate" if is_remediation else "implement",
            "artifacts": [
                f"src/{task.title.lower().replace(' ', '_')}.py",
                f"tests/test_{task.title.lower().replace(' ', '_')}.py",
            ],
            "tests_written": [
                {
                    "name": f"test_{task.title.lower().replace(' ', '_')}",
                    "status": "PASSED",
                    "type": "unit",
                }
            ],
            "tests_passed": True,
            "implementation_notes": (
                f"[DRY-RUN] {'Remediation' if is_remediation else 'Implementation'} "
                f"simulated for: {task.title}"
            ),
            "knowledge_consulted": bool(context.get("knowledge")),
            "secrets_in_code": False,
            "resource_bounded": True,
            "real_trading_disabled": True,
            "remediation_applied": is_remediation,
            "findings_addressed": (
                [f["finding_id"] for f in context.get("review_findings", [])]
                if is_remediation else []
            ),
        }
