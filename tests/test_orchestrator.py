"""Tests for the orchestration engine."""

from agent_system.config import Config
from agent_system.models import Phase, Task
from agent_system.orchestrator import Orchestrator


def test_dry_run_completes(config: Config):
    orch = Orchestrator(config)
    result = orch.dry_run()

    assert result["dry_run"] is True
    assert result["phase_result"]["status"] == "COMPLETED"
    assert result["validations"]["delegation"] is True
    assert result["validations"]["state_persistence"] is True
    assert result["validations"]["telemetry_capture"] is True
    assert result["validations"]["knowledge_capture"] is True


def test_dry_run_review_remediation(config: Config):
    orch = Orchestrator(config)
    result = orch.dry_run()

    assert result["validations"]["review_remediation"] is True
    tasks = result["phase_result"]["tasks"]
    has_remediation = any(
        t.get("remediation_cycles", 0) > 0 for t in tasks
    )
    assert has_remediation


def test_dry_run_creates_knowledge(config: Config):
    orch = Orchestrator(config)
    result = orch.dry_run()
    assert result["knowledge_entries"] > 0


def test_dry_run_telemetry_summary(config: Config):
    orch = Orchestrator(config)
    result = orch.dry_run()

    summary = result["telemetry_summary"]
    assert summary["total_events"] > 0
    assert "by_agent" in summary
    assert "by_type" in summary


def test_dry_run_unavailable_metrics(config: Config):
    config.anthropic_api_key = ""
    orch = Orchestrator(config)
    result = orch.dry_run()

    unavailable = result["unavailable_metrics"]
    assert len(unavailable) >= 2
    metrics = {m["metric"] for m in unavailable}
    assert "token_usage" in metrics


def test_dry_run_resource_limits(config: Config):
    orch = Orchestrator(config)
    result = orch.dry_run()

    res = result["resource_status"]
    assert res["max_concurrent_agents"] == 2
    assert res["active_count"] == 0


def test_execute_single_task(config: Config):
    orch = Orchestrator(config)
    config.dry_run = True
    orch.manager._dry_run = True
    orch.planner._dry_run = True
    orch.researcher._dry_run = True
    orch.engineer._dry_run = True
    orch.reviewer._dry_run = True
    orch.learner._dry_run = True

    orch.state.get_or_create_run_id()
    orch.telemetry.set_run_id(orch.state.run_id)

    phase = Phase(phase_id="TEST", name="Test Phase")
    task = Task(
        title="Single test task",
        phase_id="TEST",
        run_id=orch.state.run_id,
    )
    orch.state.save_task(task)

    result = orch.execute_task(task, phase)
    assert result["status"] == "COMPLETED"
    assert result["manager_result"] is not None
    assert result["review_result"] is not None
    assert result["learn_result"] is not None


def test_status_report(config: Config):
    orch = Orchestrator(config)
    status = orch.get_status()
    assert "current_phase" in status
    assert "resources" in status
    assert "has_resumable_state" in status
