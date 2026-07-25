"""Append-only evidence persistence for the measurement framework.

Stores structured evidence records as JSONL files (one JSON object per line).
Phase metrics are stored as a single JSON file keyed by phase_id.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from .config import Config
from .models import (
    AgentDecision,
    HumanIntervention,
    KnowledgeReuseEvent,
    PhaseMetrics,
    TestExecution,
)

logger = logging.getLogger(__name__)


class EvidenceStore:

    def __init__(self, config: Config) -> None:
        self.config = config
        self._dir = config.evidence_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _append_jsonl(self, filename: str, data: dict[str, Any]) -> None:
        path = self._dir / filename
        with open(path, "a") as f:
            f.write(json.dumps(data, default=str) + "\n")

    def _read_jsonl(self, filename: str) -> list[dict[str, Any]]:
        path = self._dir / filename
        if not path.exists():
            return []
        results = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
        return results

    def _atomic_write(self, path: Path, data: Any) -> None:
        fd, tmp = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp", prefix=".ev_"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp, str(path))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with open(path) as f:
            return json.load(f)

    # --- Human Interventions ---

    def record_human_intervention(self, intervention: HumanIntervention) -> None:
        self._append_jsonl("human_interventions.jsonl", intervention.to_dict())
        logger.info("Evidence: human intervention [%s] for task %s",
                     intervention.category.value, intervention.task_id)

    def get_human_interventions(
        self, task_id: str = "", phase_id: str = "",
    ) -> list[HumanIntervention]:
        records = self._read_jsonl("human_interventions.jsonl")
        results = []
        for r in records:
            if task_id and r.get("task_id") != task_id:
                continue
            if phase_id and r.get("phase_id") != phase_id:
                continue
            results.append(HumanIntervention.from_dict(r))
        return results

    # --- Agent Decisions ---

    def record_decision(self, decision: AgentDecision) -> None:
        self._append_jsonl("agent_decisions.jsonl", decision.to_dict())
        logger.info("Evidence: decision [%s] by %s for task %s",
                     decision.decision_type, decision.agent_role,
                     decision.task_id)

    def get_decisions(
        self, task_id: str = "", phase_id: str = "", agent_role: str = "",
    ) -> list[AgentDecision]:
        records = self._read_jsonl("agent_decisions.jsonl")
        results = []
        for r in records:
            if task_id and r.get("task_id") != task_id:
                continue
            if phase_id and r.get("phase_id") != phase_id:
                continue
            if agent_role and r.get("agent_role") != agent_role:
                continue
            results.append(AgentDecision.from_dict(r))
        return results

    # --- Test Executions ---

    def record_test_execution(self, execution: TestExecution) -> None:
        self._append_jsonl("test_executions.jsonl", execution.to_dict())
        logger.info("Evidence: test execution [%s] %d passed, %d failed",
                     execution.test_name, execution.passed, execution.failed)

    def get_test_executions(
        self, task_id: str = "", phase_id: str = "",
    ) -> list[TestExecution]:
        records = self._read_jsonl("test_executions.jsonl")
        results = []
        for r in records:
            if task_id and r.get("task_id") != task_id:
                continue
            if phase_id and r.get("phase_id") != phase_id:
                continue
            results.append(TestExecution.from_dict(r))
        return results

    # --- Knowledge Reuse Events ---

    def record_knowledge_reuse(self, event: KnowledgeReuseEvent) -> None:
        self._append_jsonl("knowledge_reuse.jsonl", event.to_dict())
        logger.info("Evidence: knowledge reuse [%s] by %s in task %s",
                     event.knowledge_title, event.agent_role, event.task_id)

    def get_knowledge_reuse_events(
        self, task_id: str = "", phase_id: str = "",
    ) -> list[KnowledgeReuseEvent]:
        records = self._read_jsonl("knowledge_reuse.jsonl")
        results = []
        for r in records:
            if task_id and r.get("task_id") != task_id:
                continue
            if phase_id and r.get("phase_id") != phase_id:
                continue
            results.append(KnowledgeReuseEvent.from_dict(r))
        return results

    # --- Phase Metrics ---

    def save_phase_metrics(self, metrics: PhaseMetrics) -> None:
        path = self._dir / "phase_metrics.json"
        data = self._read_json(path)
        if "phases" not in data:
            data["phases"] = {}
        data["phases"][metrics.phase_id] = metrics.to_dict()
        self._atomic_write(path, data)
        logger.info("Evidence: phase metrics saved for %s", metrics.phase_id)

    def get_phase_metrics(self, phase_id: str) -> PhaseMetrics | None:
        path = self._dir / "phase_metrics.json"
        data = self._read_json(path)
        phase_data = data.get("phases", {}).get(phase_id)
        if phase_data:
            return PhaseMetrics.from_dict(phase_data)
        return None

    def get_all_phase_metrics(self) -> dict[str, PhaseMetrics]:
        path = self._dir / "phase_metrics.json"
        data = self._read_json(path)
        return {
            pid: PhaseMetrics.from_dict(pdata)
            for pid, pdata in data.get("phases", {}).items()
        }
