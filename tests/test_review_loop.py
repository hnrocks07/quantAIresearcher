"""Tests for review/remediation loop."""

from agent_system.config import Config
from agent_system.models import Phase, Task
from agent_system.orchestrator import Orchestrator


def test_review_produces_findings(config: Config):
    orch = Orchestrator(config)
    orch.state.get_or_create_run_id()
    orch.telemetry.set_run_id(orch.state.run_id)

    phase = Phase(phase_id="REV_TEST", name="Review Test")
    task = Task(title="Reviewable task", phase_id="REV_TEST",
                run_id=orch.state.run_id)

    result = orch.execute_task(task, phase)
    assert len(result["findings"]) > 0


def test_remediation_triggers_on_high(config: Config):
    orch = Orchestrator(config)
    orch.state.get_or_create_run_id()
    orch.telemetry.set_run_id(orch.state.run_id)

    phase = Phase(phase_id="REM_TEST", name="Remediation Test")
    task = Task(title="Task with issues", phase_id="REM_TEST",
                run_id=orch.state.run_id)

    result = orch.execute_task(task, phase)
    assert result["remediation_cycles"] >= 1


def test_remediation_bounded(config: Config):
    config.review_remediation_max_cycles = 2
    orch = Orchestrator(config)
    orch.state.get_or_create_run_id()
    orch.telemetry.set_run_id(orch.state.run_id)

    phase = Phase(phase_id="BOUND_TEST", name="Bounded Test")
    task = Task(title="Bounded task", phase_id="BOUND_TEST",
                run_id=orch.state.run_id)

    result = orch.execute_task(task, phase)
    assert result["remediation_cycles"] <= config.review_remediation_max_cycles


def test_findings_persisted(config: Config):
    orch = Orchestrator(config)
    orch.state.get_or_create_run_id()
    orch.telemetry.set_run_id(orch.state.run_id)

    phase = Phase(phase_id="PERSIST_F", name="Persist Findings")
    task = Task(title="Findable task", phase_id="PERSIST_F",
                run_id=orch.state.run_id)

    orch.execute_task(task, phase)

    findings = orch.state.get_findings_for_task(task.task_id)
    assert len(findings) > 0


def test_handoffs_recorded_in_telemetry(config: Config):
    orch = Orchestrator(config)
    orch.state.get_or_create_run_id()
    orch.telemetry.set_run_id(orch.state.run_id)

    phase = Phase(phase_id="HO_TEST", name="Handoff Test")
    task = Task(title="Handoff task", phase_id="HO_TEST",
                run_id=orch.state.run_id)

    orch.execute_task(task, phase)

    handoffs = orch.telemetry.get_events(event_type="AGENT_HANDOFF")
    assert len(handoffs) >= 3
