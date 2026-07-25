"""Persistent state manager with atomic writes and safe resume."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from .config import Config
from .models import (
    Task, TaskStatus, Phase, PhaseStatus, ReviewFinding, _now, _uid,
)

logger = logging.getLogger(__name__)


class StateManager:

    def __init__(self, config: Config) -> None:
        self.config = config
        self._state_dir = config.state_dir
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._run_id = ""

    def _atomic_write(self, path: Path, data: Any) -> None:
        fd, tmp = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp", prefix=".state_"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp, str(path))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            return {}
        with open(path) as f:
            return json.load(f)

    # --- Run ID ---

    def get_or_create_run_id(self) -> str:
        run_file = self._state_dir / "current_run.json"
        data = self._read_json(run_file)
        if data.get("run_id") and data.get("status") != "COMPLETED":
            self._run_id = data["run_id"]
            logger.info("Resuming run %s", self._run_id)
            return self._run_id
        self._run_id = f"run_{_uid()}"
        self._atomic_write(run_file, {
            "run_id": self._run_id,
            "started_at": _now(),
            "status": "IN_PROGRESS",
        })
        logger.info("Started new run %s", self._run_id)
        return self._run_id

    def complete_run(self) -> None:
        run_file = self._state_dir / "current_run.json"
        data = self._read_json(run_file)
        data["status"] = "COMPLETED"
        data["completed_at"] = _now()
        self._atomic_write(run_file, data)

    @property
    def run_id(self) -> str:
        return self._run_id

    # --- Phase state ---

    def get_current_phase(self) -> dict:
        return self._read_json(self._state_dir / "current_phase.json")

    def set_current_phase(self, phase_id: str, status: str) -> None:
        self._atomic_write(self._state_dir / "current_phase.json", {
            "phase": phase_id,
            "status": status,
            "run_id": self._run_id,
            "updated_at": _now(),
        })

    def save_phase(self, phase: Phase) -> None:
        phases_file = self._state_dir / "phases.json"
        data = self._read_json(phases_file)
        if "phases" not in data:
            data["phases"] = {}
        data["phases"][phase.phase_id] = phase.to_dict()
        self._atomic_write(phases_file, data)

    def load_phase(self, phase_id: str) -> Phase | None:
        data = self._read_json(self._state_dir / "phases.json")
        phase_data = data.get("phases", {}).get(phase_id)
        if phase_data:
            return Phase.from_dict(phase_data)
        return None

    def get_all_phases(self) -> dict[str, Phase]:
        data = self._read_json(self._state_dir / "phases.json")
        return {
            pid: Phase.from_dict(pdata)
            for pid, pdata in data.get("phases", {}).items()
        }

    # --- Task state ---

    def save_task(self, task: Task) -> None:
        tasks_file = self._state_dir / "tasks.json"
        data = self._read_json(tasks_file)
        if "tasks" not in data:
            data["tasks"] = {}
        data["tasks"][task.task_id] = task.to_dict()
        self._atomic_write(tasks_file, data)

    def load_task(self, task_id: str) -> Task | None:
        data = self._read_json(self._state_dir / "tasks.json")
        task_data = data.get("tasks", {}).get(task_id)
        if task_data:
            return Task.from_dict(task_data)
        return None

    def get_tasks_for_phase(self, phase_id: str) -> list[Task]:
        data = self._read_json(self._state_dir / "tasks.json")
        return [
            Task.from_dict(t)
            for t in data.get("tasks", {}).values()
            if t.get("phase_id") == phase_id
        ]

    def get_active_tasks(self) -> list[Task]:
        data = self._read_json(self._state_dir / "tasks.json")
        active = [TaskStatus.IN_PROGRESS.value, TaskStatus.IN_REVIEW.value,
                   TaskStatus.REMEDIATION.value]
        return [
            Task.from_dict(t)
            for t in data.get("tasks", {}).values()
            if t.get("status") in active
        ]

    def get_pending_tasks(self, phase_id: str) -> list[Task]:
        data = self._read_json(self._state_dir / "tasks.json")
        return [
            Task.from_dict(t)
            for t in data.get("tasks", {}).values()
            if t.get("phase_id") == phase_id
            and t.get("status") == TaskStatus.PENDING.value
        ]

    def get_all_tasks(self) -> list[Task]:
        data = self._read_json(self._state_dir / "tasks.json")
        return [Task.from_dict(t) for t in data.get("tasks", {}).values()]

    # --- Review findings ---

    def save_finding(self, finding: ReviewFinding) -> None:
        findings_file = self._state_dir / "review_findings.json"
        data = self._read_json(findings_file)
        if "items" not in data:
            data["items"] = []
        existing = [i for i, f in enumerate(data["items"])
                     if f.get("finding_id") == finding.finding_id]
        if existing:
            data["items"][existing[0]] = finding.to_dict()
        else:
            data["items"].append(finding.to_dict())
        self._atomic_write(findings_file, data)

    def get_findings_for_task(self, task_id: str) -> list[ReviewFinding]:
        data = self._read_json(self._state_dir / "review_findings.json")
        return [
            ReviewFinding.from_dict(f)
            for f in data.get("items", [])
            if f.get("task_id") == task_id
        ]

    def get_open_blockers(self, task_id: str) -> list[ReviewFinding]:
        findings = self.get_findings_for_task(task_id)
        return [
            f for f in findings
            if f.status == "OPEN"
            and f.severity in (Severity.BLOCKER, Severity.HIGH)
        ]

    # --- Snapshot for resume ---

    def save_checkpoint(self) -> None:
        checkpoint = {
            "run_id": self._run_id,
            "timestamp": _now(),
            "current_phase": self.get_current_phase(),
            "active_tasks": [t.to_dict() for t in self.get_active_tasks()],
        }
        self._atomic_write(self._state_dir / "checkpoint.json", checkpoint)
        logger.info("Checkpoint saved for run %s", self._run_id)

    def load_checkpoint(self) -> dict | None:
        path = self._state_dir / "checkpoint.json"
        if path.exists():
            return self._read_json(path)
        return None

    def has_resumable_state(self) -> bool:
        run_file = self._state_dir / "current_run.json"
        data = self._read_json(run_file)
        return bool(data.get("run_id") and data.get("status") != "COMPLETED")


from .models import Severity
