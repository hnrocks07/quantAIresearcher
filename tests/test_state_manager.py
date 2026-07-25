"""Tests for state persistence and resume."""

from pathlib import Path

from agent_system.config import Config
from agent_system.models import Task, TaskStatus, Phase, PhaseStatus, ReviewFinding, Severity
from agent_system.state_manager import StateManager


def test_run_id_creation(config: Config):
    sm = StateManager(config)
    run_id = sm.get_or_create_run_id()
    assert run_id.startswith("run_")
    assert len(run_id) > 4


def test_run_id_resume(config: Config):
    sm = StateManager(config)
    first_id = sm.get_or_create_run_id()
    sm2 = StateManager(config)
    second_id = sm2.get_or_create_run_id()
    assert first_id == second_id


def test_run_id_new_after_complete(config: Config):
    sm = StateManager(config)
    first_id = sm.get_or_create_run_id()
    sm.complete_run()
    sm2 = StateManager(config)
    second_id = sm2.get_or_create_run_id()
    assert first_id != second_id


def test_task_save_load(config: Config):
    sm = StateManager(config)
    sm.get_or_create_run_id()
    task = Task(title="Test", phase_id="P1", status=TaskStatus.IN_PROGRESS)
    sm.save_task(task)

    loaded = sm.load_task(task.task_id)
    assert loaded is not None
    assert loaded.title == "Test"
    assert loaded.status == TaskStatus.IN_PROGRESS


def test_active_tasks(config: Config):
    sm = StateManager(config)
    sm.get_or_create_run_id()

    t1 = Task(title="Active", status=TaskStatus.IN_PROGRESS)
    t2 = Task(title="Done", status=TaskStatus.COMPLETED)
    t3 = Task(title="Review", status=TaskStatus.IN_REVIEW)
    sm.save_task(t1)
    sm.save_task(t2)
    sm.save_task(t3)

    active = sm.get_active_tasks()
    assert len(active) == 2
    titles = {t.title for t in active}
    assert "Active" in titles
    assert "Review" in titles


def test_phase_save_load(config: Config):
    sm = StateManager(config)
    phase = Phase(phase_id="0A", name="Evidence", status=PhaseStatus.IN_PROGRESS)
    sm.save_phase(phase)

    loaded = sm.load_phase("0A")
    assert loaded is not None
    assert loaded.name == "Evidence"
    assert loaded.status == PhaseStatus.IN_PROGRESS


def test_review_finding_save(config: Config):
    sm = StateManager(config)
    finding = ReviewFinding(
        task_id="t1",
        severity=Severity.HIGH,
        title="Test finding",
    )
    sm.save_finding(finding)

    findings = sm.get_findings_for_task("t1")
    assert len(findings) == 1
    assert findings[0].severity == Severity.HIGH


def test_checkpoint_save_load(config: Config):
    sm = StateManager(config)
    sm.get_or_create_run_id()
    sm.set_current_phase("0A", "IN_PROGRESS")
    sm.save_checkpoint()

    checkpoint = sm.load_checkpoint()
    assert checkpoint is not None
    assert checkpoint["run_id"] == sm.run_id


def test_has_resumable_state(config: Config):
    sm = StateManager(config)
    sm.get_or_create_run_id()
    assert sm.has_resumable_state()
    sm.complete_run()
    assert not sm.has_resumable_state()


def test_persistence_across_instances(config: Config):
    sm1 = StateManager(config)
    sm1.get_or_create_run_id()
    task = Task(title="Persist me", phase_id="P1")
    sm1.save_task(task)
    sm1.save_checkpoint()

    sm2 = StateManager(config)
    loaded = sm2.load_task(task.task_id)
    assert loaded is not None
    assert loaded.title == "Persist me"

    checkpoint = sm2.load_checkpoint()
    assert checkpoint is not None
