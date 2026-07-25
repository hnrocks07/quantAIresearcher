"""Tests for the metrics calculator."""

from agent_system.config import Config
from agent_system.evidence_store import EvidenceStore
from agent_system.metrics_calculator import MetricsCalculator
from agent_system.models import (
    AgentDecision,
    HumanIntervention,
    HumanInterventionCategory,
    KnowledgeReuseEvent,
    MetricType,
    Task,
    TaskStatus,
    TestExecution,
)
from agent_system.state_manager import StateManager
from agent_system.telemetry import TelemetryCollector


def _make_calculator(config: Config):
    state = StateManager(config)
    telemetry = TelemetryCollector(config)
    evidence = EvidenceStore(config)
    run_id = state.get_or_create_run_id()
    telemetry.set_run_id(run_id)
    return MetricsCalculator(config, state, telemetry, evidence), state, telemetry, evidence


def test_zero_division_safety(config: Config):
    calc, state, telemetry, evidence = _make_calculator(config)
    result = calc.compute_all()
    metrics = result["metrics"]

    assert metrics["autonomous_completion_rate"]["value"] == 0.0
    assert metrics["human_intervention_rate"]["value"] == 0.0
    assert metrics["first_pass_review_acceptance"]["value"] == 0.0
    assert metrics["test_pass_rate"]["value"] == 0.0
    assert metrics["knowledge_reuse_rate"]["value"] == 0.0


def test_autonomous_completion_rate(config: Config):
    calc, state, telemetry, evidence = _make_calculator(config)

    for i in range(4):
        task = Task(
            task_id=f"t{i}", phase_id="P1", run_id=state.run_id,
            title=f"Task {i}", status=TaskStatus.COMPLETED,
        )
        state.save_task(task)

    evidence.record_human_intervention(HumanIntervention(
        run_id=state.run_id, phase_id="P1", task_id="t0",
        category=HumanInterventionCategory.CORRECTION,
    ))

    result = calc.compute_all()
    metrics = result["metrics"]

    assert metrics["autonomous_completion_rate"]["value"] == 0.75
    assert metrics["human_intervention_rate"]["value"] == 0.25
    assert metrics["autonomous_completion_rate"]["metric_type"] == "DERIVED"


def test_first_pass_acceptance_rate(config: Config):
    calc, state, telemetry, evidence = _make_calculator(config)

    for i in range(3):
        task = Task(
            task_id=f"t{i}", phase_id="P1", run_id=state.run_id,
            title=f"Task {i}", status=TaskStatus.COMPLETED,
        )
        state.save_task(task)

    telemetry.record_event(
        event_type="REVIEW_FINDING", task_id="t0", phase_id="P1",
        details={"severity": "LOW", "title": "Minor style issue"},
    )
    telemetry.record_event(
        event_type="REVIEW_FINDING", task_id="t1", phase_id="P1",
        details={"severity": "BLOCKER", "title": "Security vulnerability"},
    )
    telemetry.record_event(
        event_type="REVIEW_FINDING", task_id="t2", phase_id="P1",
        details={"severity": "MEDIUM", "title": "Performance concern"},
    )

    result = calc.compute_all()
    metrics = result["metrics"]

    assert metrics["first_pass_review_acceptance"]["value"] == round(2 / 3, 4)


def test_all_metrics_have_metric_type(config: Config):
    calc, state, telemetry, evidence = _make_calculator(config)
    result = calc.compute_all()

    for name, metric in result["metrics"].items():
        assert "metric_type" in metric, f"Metric {name} missing metric_type"
        assert metric["metric_type"] in (
            "MEASURED", "DERIVED", "ESTIMATED", "UNAVAILABLE"
        ), f"Metric {name} has invalid metric_type: {metric['metric_type']}"


def test_unavailable_metrics_without_api_key(config: Config):
    config.anthropic_api_key = ""
    calc, state, telemetry, evidence = _make_calculator(config)

    telemetry.record_event("TASK_START", status="OK")

    result = calc.compute_all()
    metrics = result["metrics"]

    assert metrics["model_token_usage"]["metric_type"] == "UNAVAILABLE"
    assert metrics["model_cost"]["metric_type"] == "UNAVAILABLE"


def test_test_pass_rate(config: Config):
    calc, state, telemetry, evidence = _make_calculator(config)

    evidence.record_test_execution(TestExecution(
        run_id=state.run_id, phase_id="P1", task_id="T1",
        test_name="unit_tests", passed=8, failed=2,
    ))
    evidence.record_test_execution(TestExecution(
        run_id=state.run_id, phase_id="P1", task_id="T2",
        test_name="integration_tests", passed=5, failed=0,
    ))

    result = calc.compute_all()
    metrics = result["metrics"]

    assert metrics["test_pass_rate"]["value"] == round(13 / 15, 4)


def test_knowledge_reuse_rate(config: Config):
    calc, state, telemetry, evidence = _make_calculator(config)

    for i in range(5):
        state.save_task(Task(
            task_id=f"t{i}", phase_id="P1", run_id=state.run_id,
            title=f"Task {i}", status=TaskStatus.COMPLETED,
        ))

    evidence.record_knowledge_reuse(KnowledgeReuseEvent(
        run_id=state.run_id, phase_id="P1", task_id="t0",
        knowledge_entry_id="ke1", knowledge_title="Pattern A",
    ))
    evidence.record_knowledge_reuse(KnowledgeReuseEvent(
        run_id=state.run_id, phase_id="P1", task_id="t1",
        knowledge_entry_id="ke2", knowledge_title="Pattern B",
    ))

    result = calc.compute_all()
    metrics = result["metrics"]

    assert metrics["knowledge_reuse_rate"]["value"] == 0.4


def test_compute_phase_metrics(config: Config):
    calc, state, telemetry, evidence = _make_calculator(config)

    for i in range(3):
        state.save_task(Task(
            task_id=f"t{i}", phase_id="P1", run_id=state.run_id,
            title=f"Task {i}",
            status=TaskStatus.COMPLETED if i < 2 else TaskStatus.FAILED,
            remediation_cycles=1 if i == 0 else 0,
        ))

    evidence.record_decision(AgentDecision(
        run_id=state.run_id, phase_id="P1", task_id="t0",
        agent_role="Manager", decision_type="EVAL", decision="go",
    ))

    phase_metrics = calc.compute_phase_metrics("P1")
    assert phase_metrics.task_count == 3
    assert phase_metrics.tasks_completed == 2
    assert phase_metrics.tasks_failed == 1
    assert phase_metrics.remediation_cycles == 1
    assert phase_metrics.agent_decision_count == 1
