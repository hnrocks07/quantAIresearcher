"""Tests for telemetry and evidence framework."""

from agent_system.config import Config
from agent_system.models import MetricType, AgentHandoff
from agent_system.telemetry import TelemetryCollector


def test_record_event(config: Config):
    tc = TelemetryCollector(config)
    tc.set_run_id("test_run_1")

    event = tc.record_event(
        event_type="TEST_EVENT",
        phase_id="P1",
        task_id="T1",
        agent_role="TestAgent",
        status="COMPLETED",
    )

    assert event.event_type == "TEST_EVENT"
    assert event.run_id == "test_run_1"
    assert event.metric_type == MetricType.MEASURED


def test_timed_operation(config: Config):
    tc = TelemetryCollector(config)
    tc.set_run_id("test_run_2")

    with tc.timed_operation("TIMED_TEST", phase_id="P1") as ctx:
        ctx["status"] = "COMPLETED"
        ctx["details"] = {"result": "ok"}

    events = tc.get_events(event_type="TIMED_TEST")
    assert len(events) == 1
    assert events[0].duration_seconds >= 0
    assert events[0].status == "COMPLETED"


def test_timed_operation_failure(config: Config):
    tc = TelemetryCollector(config)
    tc.set_run_id("test_run_3")

    try:
        with tc.timed_operation("FAIL_TEST"):
            raise ValueError("test error")
    except ValueError:
        pass

    events = tc.get_events(event_type="FAIL_TEST")
    assert len(events) == 1
    assert events[0].status == "FAILED"
    assert "test error" in events[0].error


def test_handoff_recording(config: Config):
    tc = TelemetryCollector(config)
    tc.set_run_id("test_run_4")

    handoff = AgentHandoff(
        from_agent="PlannerAgent",
        to_agent="SeniorEngineerAgent",
        task_id="T1",
        phase_id="P1",
        context_summary="Ready for implementation",
    )
    tc.record_handoff(handoff)

    events = tc.get_events(event_type="AGENT_HANDOFF")
    assert len(events) == 1
    assert events[0].handoff_from == "PlannerAgent"
    assert events[0].handoff_to == "SeniorEngineerAgent"


def test_metric_type_classification(config: Config):
    tc = TelemetryCollector(config)
    tc.set_run_id("test_run_5")

    tc.record_event("E1", metric_type=MetricType.MEASURED)
    tc.record_event("E2", metric_type=MetricType.DERIVED)
    tc.record_event("E3", metric_type=MetricType.ESTIMATED)
    tc.record_event("E4", metric_type=MetricType.UNAVAILABLE)

    events = tc.get_events()
    types = {e.event_type: e.metric_type for e in events}
    assert types["E1"] == MetricType.MEASURED
    assert types["E2"] == MetricType.DERIVED
    assert types["E3"] == MetricType.ESTIMATED
    assert types["E4"] == MetricType.UNAVAILABLE


def test_summary_generation(config: Config):
    tc = TelemetryCollector(config)
    tc.set_run_id("test_run_6")

    tc.record_event("TASK_START", agent_role="PlannerAgent", status="OK")
    tc.record_event("TASK_FAIL", agent_role="EngineerAgent", status="FAILED")
    tc.record_event("AGENT_HANDOFF", handoff_from="A", handoff_to="B")

    summary = tc.generate_summary()
    assert summary["total_events"] == 3
    assert summary["failures"] == 1
    assert summary["handoffs"] == 1
    assert summary["metric_type"] == "DERIVED"


def test_unavailable_metrics_no_api_key(config: Config):
    config.anthropic_api_key = ""
    tc = TelemetryCollector(config)
    unavailable = tc.get_unavailable_metrics()
    assert len(unavailable) >= 2
    metrics = {m["metric"] for m in unavailable}
    assert "token_usage" in metrics
    assert "cost" in metrics


def test_persist_to_disk(config: Config):
    tc = TelemetryCollector(config)
    tc.set_run_id("test_run_7")
    tc.record_event("PERSIST_TEST", status="OK")

    tc2 = TelemetryCollector(config)
    events = tc2.load_events_from_disk("test_run_7")
    assert len(events) == 1
    assert events[0].event_type == "PERSIST_TEST"
