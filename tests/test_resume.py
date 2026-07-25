"""Tests for persistence and resume after restart."""

from agent_system.config import Config
from agent_system.models import Task, TaskStatus, Phase, PhaseStatus
from agent_system.orchestrator import Orchestrator
from agent_system.state_manager import StateManager


def test_state_survives_new_instance(config: Config):
    sm1 = StateManager(config)
    run_id = sm1.get_or_create_run_id()
    task = Task(title="Survive", phase_id="P1", status=TaskStatus.IN_PROGRESS)
    sm1.save_task(task)
    phase = Phase(phase_id="P1", name="Test", status=PhaseStatus.IN_PROGRESS)
    sm1.save_phase(phase)
    sm1.set_current_phase("P1", "IN_PROGRESS")
    sm1.save_checkpoint()

    sm2 = StateManager(config)
    resumed_id = sm2.get_or_create_run_id()
    assert resumed_id == run_id

    loaded_task = sm2.load_task(task.task_id)
    assert loaded_task is not None
    assert loaded_task.status == TaskStatus.IN_PROGRESS

    loaded_phase = sm2.load_phase("P1")
    assert loaded_phase is not None
    assert loaded_phase.status == PhaseStatus.IN_PROGRESS

    checkpoint = sm2.load_checkpoint()
    assert checkpoint is not None
    assert checkpoint["current_phase"]["phase"] == "P1"


def test_orchestrator_resume_detection(config: Config):
    orch1 = Orchestrator(config)
    orch1.state.get_or_create_run_id()
    orch1.state.set_current_phase("TEST", "IN_PROGRESS")
    orch1.state.save_checkpoint()

    orch2 = Orchestrator(config)
    status = orch2.get_status()
    assert status["has_resumable_state"] is True


def test_completed_run_no_resume(config: Config):
    orch = Orchestrator(config)
    result = orch.dry_run()

    orch.state.complete_run()
    status = orch.get_status()
    assert status["has_resumable_state"] is False


def test_knowledge_persists_across_runs(config: Config):
    orch1 = Orchestrator(config)
    result1 = orch1.dry_run()
    count1 = orch1.knowledge.count()
    assert count1 > 0

    orch2 = Orchestrator(config)
    count2 = orch2.knowledge.count()
    assert count2 == count1


def test_telemetry_persists_to_disk(config: Config):
    orch = Orchestrator(config)
    result = orch.dry_run()
    run_id = result["run_id"]

    from agent_system.telemetry import TelemetryCollector
    tc = TelemetryCollector(config)
    events = tc.load_events_from_disk(run_id)
    assert len(events) > 0
