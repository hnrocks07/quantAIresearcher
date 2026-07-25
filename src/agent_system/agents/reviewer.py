"""Reviewer Agent - independent review with severity classification."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import AgentRole, Task, Severity, _uid
from .base import BaseAgent


class ReviewerAgent(BaseAgent):

    role = AgentRole.REVIEWER
    system_prompt = (
        "You are the Reviewer. Independently review correctness, local data "
        "ownership, provenance/licensing, reproducibility, bias, Pine parity "
        "claims, timestamps, fees/slippage/fills, security, memory/disk, "
        "tests/logs/docs. Classify findings as BLOCKER/HIGH/MEDIUM/LOW. "
        "Also review evidence integrity: verify agent claims are supported "
        "by tests/artifacts, and that measured vs estimated metrics are "
        "labeled correctly."
    )

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def execute(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(task, context)
        is_re_review = bool(context.get("review_findings"))
        action = "re_review" if is_re_review else "review"
        prompt += (
            "\n\nRespond with ONLY a JSON object (no markdown, no explanation) "
            "with these fields:\n"
            f'- "action": "{action}"\n'
            '- "findings": list of finding objects (empty list if no issues), each with:\n'
            '  - "finding_id": unique string\n'
            '  - "category": string (e.g. "correctness", "security", "testing", '
            '"documentation", "architecture", "licensing")\n'
            '  - "severity": "BLOCKER", "HIGH", "MEDIUM", or "LOW"\n'
            '  - "title": short finding title\n'
            '  - "description": detailed description\n'
            '  - "recommendation": what to fix\n'
            '  - "status": "OPEN"\n'
            '- "blockers_found": count of BLOCKER+HIGH severity findings\n'
            '- "total_findings": total count of findings\n'
            '- "evidence_integrity_check": {\n'
            '    "claims_supported_by_artifacts": boolean,\n'
            '    "metric_types_correctly_labeled": boolean,\n'
            '    "no_fabricated_telemetry": boolean\n'
            '  }\n'
            '- "recommendation": "APPROVED" or "REMEDIATE"\n'
        )
        return self._call_llm(self.system_prompt, prompt)

    def dry_run_response(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        is_re_review = bool(context.get("review_findings"))
        findings = []
        if not is_re_review:
            findings = [
                {
                    "finding_id": _uid(),
                    "category": "testing",
                    "severity": Severity.HIGH.value,
                    "title": f"[DRY-RUN] Additional edge-case tests needed for {task.title}",
                    "description": "Simulated review finding requiring remediation",
                    "recommendation": "Add boundary condition tests",
                    "status": "OPEN",
                },
                {
                    "finding_id": _uid(),
                    "category": "documentation",
                    "severity": Severity.LOW.value,
                    "title": "[DRY-RUN] Minor documentation gap",
                    "description": "Simulated low-severity finding",
                    "recommendation": "Add inline documentation",
                    "status": "OPEN",
                },
            ]
        return {
            "action": "re_review" if is_re_review else "review",
            "findings": findings,
            "blockers_found": sum(
                1 for f in findings
                if f["severity"] in (Severity.BLOCKER.value, Severity.HIGH.value)
            ),
            "total_findings": len(findings),
            "evidence_integrity_check": {
                "claims_supported_by_artifacts": True,
                "metric_types_correctly_labeled": True,
                "no_fabricated_telemetry": True,
            },
            "recommendation": (
                "APPROVED" if is_re_review or not findings
                else "REMEDIATE"
            ),
        }
