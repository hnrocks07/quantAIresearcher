"""Tests for the evidence store persistence layer."""

from agent_system.config import Config
from agent_system.evidence_store import EvidenceStore
from agent_system.models import (
    AgentDecision,
    HumanIntervention,
    HumanInterventionCategory,
    KnowledgeReuseEvent,
    MetricType,
    PhaseMetrics,
    TestExecution,
)


def test_record_human_intervention(config: Config):
    store = EvidenceStore(config)
    intervention = HumanIntervention(
        run_id="run_1",
        phase_id="P1",
        task_id="T1",
        category=HumanInterventionCategory.APPROVAL,
        agent_role="EngineeringManagerAgent",
        reason="Phase deliverables need sign-off",
        decision="Approved",
        impact="Phase continues to next step",
    )
    store.record_human_intervention(intervention)

    results = store.get_human_interventions(task_id="T1")
    assert len(results) == 1
    assert results[0].category == HumanInterventionCategory.APPROVAL
    assert results[0].reason == "Phase deliverables need sign-off"


def test_record_agent_decision(config: Config):
    store = EvidenceStore(config)
    decision = AgentDecision(
        run_id="run_1",
        phase_id="P1",
        task_id="T1",
        agent_role="EngineeringManagerAgent",
        decision_type="TASK_EVALUATION",
        decision="direct_implementation",
        alternatives=["research_first", "skip_task"],
        rationale="Task is straightforward, no research needed",
        confidence="HIGH",
    )
    store.record_decision(decision)

    results = store.get_decisions(task_id="T1")
    assert len(results) == 1
    assert results[0].decision_type == "TASK_EVALUATION"
    assert results[0].decision == "direct_implementation"
    assert len(results[0].alternatives) == 2


def test_record_test_execution(config: Config):
    store = EvidenceStore(config)
    execution = TestExecution(
        run_id="run_1",
        phase_id="P1",
        task_id="T1",
        test_name="test_core_logic",
        passed=10,
        failed=2,
        skipped=1,
        duration_seconds=3.5,
    )
    store.record_test_execution(execution)

    results = store.get_test_executions(task_id="T1")
    assert len(results) == 1
    assert results[0].passed == 10
    assert results[0].failed == 2
    assert results[0].total == 13


def test_record_knowledge_reuse(config: Config):
    store = EvidenceStore(config)
    event = KnowledgeReuseEvent(
        run_id="run_1",
        phase_id="P2",
        task_id="T5",
        agent_role="SeniorEngineerAgent",
        knowledge_entry_id="ke_123",
        knowledge_title="Atomic write pattern",
        source_phase="P1",
        application="Applied atomic write to new state file",
        outcome="Implementation matches established pattern",
    )
    store.record_knowledge_reuse(event)

    results = store.get_knowledge_reuse_events(phase_id="P2")
    assert len(results) == 1
    assert results[0].knowledge_entry_id == "ke_123"
    assert results[0].source_phase == "P1"


def test_save_and_load_phase_metrics(config: Config):
    store = EvidenceStore(config)
    metrics = PhaseMetrics(
        phase_id="P1",
        run_id="run_1",
        task_count=5,
        tasks_completed=4,
        tasks_failed=1,
        remediation_cycles=2,
        findings_count=3,
        findings_blocker=1,
        findings_high=2,
        test_pass_count=20,
        test_fail_count=1,
    )
    store.save_phase_metrics(metrics)

    loaded = store.get_phase_metrics("P1")
    assert loaded is not None
    assert loaded.task_count == 5
    assert loaded.tasks_completed == 4
    assert loaded.tasks_failed == 1
    assert loaded.findings_blocker == 1
    assert loaded.metric_type == MetricType.DERIVED


def test_append_only_persistence(config: Config):
    store = EvidenceStore(config)

    store.record_decision(AgentDecision(
        run_id="run_1", phase_id="P1", task_id="T1",
        agent_role="Manager", decision_type="EVAL", decision="go",
    ))
    store.record_decision(AgentDecision(
        run_id="run_1", phase_id="P1", task_id="T2",
        agent_role="Reviewer", decision_type="VERDICT", decision="approved",
    ))

    all_decisions = store.get_decisions(phase_id="P1")
    assert len(all_decisions) == 2

    store2 = EvidenceStore(config)
    reloaded = store2.get_decisions(phase_id="P1")
    assert len(reloaded) == 2


def test_filter_by_phase(config: Config):
    store = EvidenceStore(config)

    store.record_human_intervention(HumanIntervention(
        phase_id="P1", task_id="T1",
        category=HumanInterventionCategory.CORRECTION,
    ))
    store.record_human_intervention(HumanIntervention(
        phase_id="P2", task_id="T2",
        category=HumanInterventionCategory.CLARIFICATION,
    ))

    p1 = store.get_human_interventions(phase_id="P1")
    assert len(p1) == 1
    assert p1[0].category == HumanInterventionCategory.CORRECTION

    p2 = store.get_human_interventions(phase_id="P2")
    assert len(p2) == 1
    assert p2[0].category == HumanInterventionCategory.CLARIFICATION


def test_phase_metrics_overwrite(config: Config):
    store = EvidenceStore(config)

    store.save_phase_metrics(PhaseMetrics(
        phase_id="P1", task_count=3, tasks_completed=2,
    ))
    store.save_phase_metrics(PhaseMetrics(
        phase_id="P1", task_count=5, tasks_completed=5,
    ))

    loaded = store.get_phase_metrics("P1")
    assert loaded.task_count == 5
    assert loaded.tasks_completed == 5


def test_get_all_phase_metrics(config: Config):
    store = EvidenceStore(config)

    store.save_phase_metrics(PhaseMetrics(phase_id="P1", task_count=3))
    store.save_phase_metrics(PhaseMetrics(phase_id="P2", task_count=7))

    all_metrics = store.get_all_phase_metrics()
    assert len(all_metrics) == 2
    assert all_metrics["P1"].task_count == 3
    assert all_metrics["P2"].task_count == 7
