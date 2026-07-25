"""Computes derived metrics from raw evidence.

Every metric is tagged with its MetricType classification:
MEASURED, DERIVED, ESTIMATED, or UNAVAILABLE.
"""

from __future__ import annotations

from typing import Any

from .config import Config
from .evidence_store import EvidenceStore
from .models import MetricType, PhaseMetrics
from .state_manager import StateManager
from .telemetry import TelemetryCollector


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _metric(name: str, value: Any, metric_type: MetricType,
            description: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "metric_type": metric_type.value,
        "description": description,
    }


class MetricsCalculator:

    def __init__(self, config: Config, state: StateManager,
                 telemetry: TelemetryCollector,
                 evidence: EvidenceStore) -> None:
        self.config = config
        self.state = state
        self.telemetry = telemetry
        self.evidence = evidence

    def compute_all(self, run_id: str = "") -> dict[str, Any]:
        tasks = self.state.get_all_tasks()
        rid = run_id or self.state.run_id
        events = self.telemetry.load_events_from_disk(rid) if rid else []
        if not events:
            events = self.telemetry.get_events()
        all_interventions = self.evidence.get_human_interventions()
        all_decisions = self.evidence.get_decisions()
        all_tests = self.evidence.get_test_executions()
        all_reuse = self.evidence.get_knowledge_reuse_events()

        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.status.value == "COMPLETED")
        failed_tasks = sum(1 for t in tasks if t.status.value == "FAILED")
        intervention_task_ids = {i.task_id for i in all_interventions}
        tasks_with_intervention = sum(
            1 for t in tasks if t.task_id in intervention_task_ids
        )
        autonomous_completed = completed_tasks - tasks_with_intervention

        review_events = [e for e in events if e.event_type == "REVIEW_FINDING"]
        reviewed_task_ids = {e.task_id for e in review_events}
        total_reviewed = len(reviewed_task_ids)

        first_pass_accepted = 0
        for tid in reviewed_task_ids:
            task_findings = [e for e in review_events if e.task_id == tid]
            blockers = [
                f for f in task_findings
                if f.details.get("severity") in ("BLOCKER", "HIGH")
            ]
            if not blockers:
                first_pass_accepted += 1

        total_findings = len(review_events)
        remediation_events = [
            e for e in events if e.event_type == "REMEDIATION_CYCLE"
        ]
        total_remediations = len(remediation_events)

        total_retries = sum(e.retries for e in events)
        failed_events = sum(1 for e in events if e.status == "FAILED")
        recovered = total_retries - failed_events if total_retries > failed_events else 0

        total_test_passed = sum(t.passed for t in all_tests)
        total_test_failed = sum(t.failed for t in all_tests)
        total_test_total = total_test_passed + total_test_failed

        tasks_with_reuse = len({r.task_id for r in all_reuse})

        total_duration = sum(e.duration_seconds for e in events)

        has_tokens = any(bool(e.token_usage) for e in events)
        has_cost = any(bool(e.cost) for e in events)

        metrics = [
            _metric(
                "autonomous_completion_rate",
                _safe_rate(autonomous_completed, total_tasks),
                MetricType.DERIVED,
                "Tasks completed without human intervention / total tasks",
            ),
            _metric(
                "human_intervention_rate",
                _safe_rate(tasks_with_intervention, total_tasks),
                MetricType.DERIVED,
                "Tasks with human intervention / total tasks",
            ),
            _metric(
                "first_pass_review_acceptance",
                _safe_rate(first_pass_accepted, total_reviewed),
                MetricType.DERIVED,
                "Tasks approved on first review (no BLOCKER/HIGH findings) / total reviewed",
            ),
            _metric(
                "reviewer_defect_discovery_rate",
                _safe_rate(total_findings, total_reviewed),
                MetricType.DERIVED,
                "Review findings / tasks reviewed",
            ),
            _metric(
                "autonomous_remediation_rate",
                _safe_rate(total_remediations, total_findings),
                MetricType.DERIVED,
                "Remediation cycles / total findings needing remediation",
            ),
            _metric(
                "retry_failure_recovery_rate",
                _safe_rate(recovered, total_retries),
                MetricType.DERIVED,
                "Recovered retries / total retries",
            ),
            _metric(
                "total_duration_seconds",
                round(total_duration, 3),
                MetricType.MEASURED,
                "Total wall-clock time across all events",
            ),
            _metric(
                "model_token_usage",
                {"metric_type": MetricType.MEASURED.value} if has_tokens
                else {"metric_type": MetricType.UNAVAILABLE.value},
                MetricType.MEASURED if has_tokens else MetricType.UNAVAILABLE,
                "Total token usage from Claude API responses",
            ),
            _metric(
                "model_cost",
                {"metric_type": MetricType.MEASURED.value} if has_cost
                else {"metric_type": MetricType.UNAVAILABLE.value},
                MetricType.MEASURED if has_cost else MetricType.UNAVAILABLE,
                "Total cost from Claude API responses",
            ),
            _metric(
                "test_pass_rate",
                _safe_rate(total_test_passed, total_test_total),
                MetricType.DERIVED,
                "Test passed / total test executions",
            ),
            _metric(
                "knowledge_reuse_rate",
                _safe_rate(tasks_with_reuse, total_tasks),
                MetricType.DERIVED,
                "Tasks using prior knowledge / total tasks",
            ),
            _metric(
                "total_tasks", total_tasks,
                MetricType.MEASURED, "Total tasks across all phases",
            ),
            _metric(
                "completed_tasks", completed_tasks,
                MetricType.MEASURED, "Tasks completed successfully",
            ),
            _metric(
                "failed_tasks", failed_tasks,
                MetricType.MEASURED, "Tasks that failed",
            ),
            _metric(
                "human_intervention_count", len(all_interventions),
                MetricType.MEASURED, "Total human intervention records",
            ),
            _metric(
                "agent_decision_count", len(all_decisions),
                MetricType.MEASURED, "Total agent decision records",
            ),
        ]

        return {
            "run_id": run_id or self.state.run_id,
            "metrics": {m["name"]: m for m in metrics},
        }

    def compute_phase_metrics(self, phase_id: str) -> PhaseMetrics:
        tasks = self.state.get_tasks_for_phase(phase_id)
        interventions = self.evidence.get_human_interventions(phase_id=phase_id)
        decisions = self.evidence.get_decisions(phase_id=phase_id)
        tests = self.evidence.get_test_executions(phase_id=phase_id)
        reuse = self.evidence.get_knowledge_reuse_events(phase_id=phase_id)

        completed = sum(1 for t in tasks if t.status.value == "COMPLETED")
        failed = sum(1 for t in tasks if t.status.value == "FAILED")
        total_duration = sum(
            float(t.completed_at or "0") - float(t.started_at or "0")
            for t in tasks
            if t.started_at and t.completed_at
            and t.started_at.replace(".", "").replace("-", "").replace(":", "").replace("T", "").replace("+", "").replace("Z", "").isdigit() is False
        )

        findings = self.state.get_findings_for_task("")
        phase_findings = [f for f in findings if f.phase_id == phase_id] if phase_id else []

        return PhaseMetrics(
            phase_id=phase_id,
            run_id=self.state.run_id,
            task_count=len(tasks),
            tasks_completed=completed,
            tasks_failed=failed,
            total_duration_seconds=0.0,
            remediation_cycles=sum(t.remediation_cycles for t in tasks),
            findings_count=len(phase_findings),
            findings_blocker=sum(
                1 for f in phase_findings if f.severity.value == "BLOCKER"
            ),
            findings_high=sum(
                1 for f in phase_findings if f.severity.value == "HIGH"
            ),
            knowledge_entries_created=0,
            knowledge_reuse_count=len(reuse),
            human_intervention_count=len(interventions),
            agent_decision_count=len(decisions),
            test_pass_count=sum(t.passed for t in tests),
            test_fail_count=sum(t.failed for t in tests),
        )
