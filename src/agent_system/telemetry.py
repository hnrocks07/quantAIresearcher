"""Telemetry and evidence capture framework.

Every metric is classified as MEASURED, DERIVED, ESTIMATED, or UNAVAILABLE.
Never fabricates telemetry data.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from .config import Config
from .models import (
    TelemetryEvent, MetricType, AgentHandoff, _now, _uid,
)

logger = logging.getLogger(__name__)


class TelemetryCollector:

    def __init__(self, config: Config) -> None:
        self.config = config
        self._dir = config.telemetry_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._events: list[TelemetryEvent] = []
        self._run_id = ""

    def set_run_id(self, run_id: str) -> None:
        self._run_id = run_id

    def _event_file(self) -> Path:
        return self._dir / f"events_{self._run_id}.jsonl"

    def _append_event(self, event: TelemetryEvent) -> None:
        self._events.append(event)
        with open(self._event_file(), "a") as f:
            f.write(json.dumps(event.to_dict(), default=str) + "\n")

    def record_event(
        self,
        event_type: str,
        phase_id: str = "",
        task_id: str = "",
        agent_role: str = "",
        status: str = "",
        duration_seconds: float = 0.0,
        details: dict[str, Any] | None = None,
        metric_type: MetricType = MetricType.MEASURED,
        model_identifier: str = "",
        token_usage: dict[str, Any] | None = None,
        cost: dict[str, Any] | None = None,
        artifacts: list[str] | None = None,
        handoff_from: str = "",
        handoff_to: str = "",
        human_intervention: bool = False,
        human_intervention_reason: str = "",
        knowledge_retrieved: list[str] | None = None,
        knowledge_stored: list[str] | None = None,
        error: str = "",
        retries: int = 0,
    ) -> TelemetryEvent:
        event = TelemetryEvent(
            run_id=self._run_id,
            phase_id=phase_id,
            task_id=task_id,
            agent_role=agent_role,
            event_type=event_type,
            status=status,
            duration_seconds=duration_seconds,
            details=details or {},
            metric_type=metric_type,
            model_identifier=model_identifier,
            token_usage=token_usage or {},
            cost=cost or {},
            artifacts=artifacts or [],
            handoff_from=handoff_from,
            handoff_to=handoff_to,
            human_intervention=human_intervention,
            human_intervention_reason=human_intervention_reason,
            knowledge_retrieved=knowledge_retrieved or [],
            knowledge_stored=knowledge_stored or [],
            error=error,
            retries=retries,
        )
        self._append_event(event)
        return event

    def record_handoff(self, handoff: AgentHandoff) -> None:
        self.record_event(
            event_type="AGENT_HANDOFF",
            phase_id=handoff.phase_id,
            task_id=handoff.task_id,
            handoff_from=handoff.from_agent,
            handoff_to=handoff.to_agent,
            details={"context_summary": handoff.context_summary,
                      "artifacts_passed": handoff.artifacts_passed},
        )

    @contextmanager
    def timed_operation(
        self,
        event_type: str,
        phase_id: str = "",
        task_id: str = "",
        agent_role: str = "",
    ) -> Generator[dict[str, Any], None, None]:
        context: dict[str, Any] = {"status": "IN_PROGRESS", "details": {}}
        start = time.monotonic()
        try:
            yield context
            duration = time.monotonic() - start
            self.record_event(
                event_type=event_type,
                phase_id=phase_id,
                task_id=task_id,
                agent_role=agent_role,
                status=context.get("status", "COMPLETED"),
                duration_seconds=round(duration, 3),
                details=context.get("details", {}),
                metric_type=MetricType.MEASURED,
            )
        except Exception as e:
            duration = time.monotonic() - start
            self.record_event(
                event_type=event_type,
                phase_id=phase_id,
                task_id=task_id,
                agent_role=agent_role,
                status="FAILED",
                duration_seconds=round(duration, 3),
                error=str(e),
                metric_type=MetricType.MEASURED,
            )
            raise

    def get_events(
        self,
        run_id: str = "",
        phase_id: str = "",
        task_id: str = "",
        event_type: str = "",
    ) -> list[TelemetryEvent]:
        results = []
        for event in self._events:
            if run_id and event.run_id != run_id:
                continue
            if phase_id and event.phase_id != phase_id:
                continue
            if task_id and event.task_id != task_id:
                continue
            if event_type and event.event_type != event_type:
                continue
            results.append(event)
        return results

    def load_events_from_disk(self, run_id: str = "") -> list[TelemetryEvent]:
        rid = run_id or self._run_id
        path = self._dir / f"events_{rid}.jsonl"
        if not path.exists():
            return []
        events = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(TelemetryEvent.from_dict(json.loads(line)))
        return events

    def generate_summary(self, run_id: str = "") -> dict[str, Any]:
        events = self.load_events_from_disk(run_id) if run_id else self._events
        if not events:
            return {"status": "no_events", "metric_type": "MEASURED"}

        summary: dict[str, Any] = {
            "total_events": len(events),
            "metric_type": "DERIVED",
            "by_type": {},
            "by_agent": {},
            "failures": 0,
            "retries": 0,
            "human_interventions": 0,
            "handoffs": 0,
            "total_duration_seconds": 0.0,
            "token_usage": {"metric_type": "UNAVAILABLE"},
            "cost": {"metric_type": "UNAVAILABLE"},
        }

        has_tokens = False
        has_cost = False

        for ev in events:
            t = ev.event_type
            summary["by_type"][t] = summary["by_type"].get(t, 0) + 1

            if ev.agent_role:
                summary["by_agent"][ev.agent_role] = (
                    summary["by_agent"].get(ev.agent_role, 0) + 1
                )
            if ev.status == "FAILED":
                summary["failures"] += 1
            summary["retries"] += ev.retries
            if ev.human_intervention:
                summary["human_interventions"] += 1
            if ev.event_type == "AGENT_HANDOFF":
                summary["handoffs"] += 1
            summary["total_duration_seconds"] += ev.duration_seconds

            if ev.token_usage:
                has_tokens = True
            if ev.cost:
                has_cost = True

        if has_tokens:
            summary["token_usage"]["metric_type"] = "MEASURED"
        if has_cost:
            summary["cost"]["metric_type"] = "MEASURED"

        summary["total_duration_seconds"] = round(
            summary["total_duration_seconds"], 3
        )
        return summary

    def get_unavailable_metrics(self) -> list[dict[str, str]]:
        unavailable = []
        if not self.config.has_api_key:
            unavailable.extend([
                {"metric": "token_usage", "reason": "No API key configured; "
                 "running in dry-run or CLI mode",
                 "metric_type": "UNAVAILABLE"},
                {"metric": "cost", "reason": "Cannot derive cost without "
                 "token usage data", "metric_type": "UNAVAILABLE"},
                {"metric": "model_identifier_from_api",
                 "reason": "Model identity from API response headers "
                 "not available in current mode",
                 "metric_type": "UNAVAILABLE"},
            ])
        return unavailable
