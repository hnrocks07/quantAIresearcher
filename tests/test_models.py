"""Tests for core data models."""

from agent_system.models import (
    Task, TaskStatus, Phase, PhaseStatus, ReviewFinding, Severity,
    TelemetryEvent, MetricType, KnowledgeEntry, AgentRole,
)


def test_task_create_and_serialize():
    task = Task(title="Test task", description="A test")
    d = task.to_dict()
    assert d["title"] == "Test task"
    assert d["status"] == "PENDING"
    assert task.task_id


def test_task_roundtrip():
    task = Task(
        title="Roundtrip",
        status=TaskStatus.IN_PROGRESS,
        phase_id="P1",
        retries=2,
    )
    d = task.to_dict()
    restored = Task.from_dict(d)
    assert restored.title == "Roundtrip"
    assert restored.status == TaskStatus.IN_PROGRESS
    assert restored.retries == 2


def test_phase_roundtrip():
    phase = Phase(
        phase_id="0A",
        name="Evidence Framework",
        status=PhaseStatus.IN_PROGRESS,
        dependencies=["BOOTSTRAP"],
    )
    d = phase.to_dict()
    restored = Phase.from_dict(d)
    assert restored.phase_id == "0A"
    assert restored.status == PhaseStatus.IN_PROGRESS
    assert restored.dependencies == ["BOOTSTRAP"]


def test_review_finding_severity():
    finding = ReviewFinding(
        severity=Severity.BLOCKER,
        title="Critical bug",
        category="correctness",
    )
    d = finding.to_dict()
    assert d["severity"] == "BLOCKER"
    restored = ReviewFinding.from_dict(d)
    assert restored.severity == Severity.BLOCKER


def test_telemetry_event_metric_type():
    event = TelemetryEvent(
        event_type="TEST",
        metric_type=MetricType.MEASURED,
    )
    d = event.to_dict()
    assert d["metric_type"] == "MEASURED"
    restored = TelemetryEvent.from_dict(d)
    assert restored.metric_type == MetricType.MEASURED


def test_knowledge_entry_roundtrip():
    entry = KnowledgeEntry(
        category="pattern",
        title="Test pattern",
        tags=["test", "phase_0"],
    )
    d = entry.to_dict()
    restored = KnowledgeEntry.from_dict(d)
    assert restored.title == "Test pattern"
    assert restored.tags == ["test", "phase_0"]


def test_agent_roles():
    roles = list(AgentRole)
    assert len(roles) == 6
    assert AgentRole.ENGINEERING_MANAGER.value == "EngineeringManagerAgent"
