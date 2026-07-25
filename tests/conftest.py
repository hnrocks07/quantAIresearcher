"""Shared test fixtures."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from agent_system.config import Config


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    project = tmp_path / "test_project"
    project.mkdir()
    for d in ["state", "knowledge", "phases", "agents", "logs",
              "telemetry", "artifacts", "evidence"]:
        (project / d).mkdir()

    (project / "state" / "project_config.json").write_text(
        '{"model":"claude","max_concurrent_llm_agents":2,'
        '"real_money_trading":false,"agent_team_proof":true,'
        '"tracked_model_telemetry":"capture_if_available_never_fabricate"}'
    )
    (project / "state" / "current_phase.json").write_text(
        '{"phase":"BOOTSTRAP","status":"NOT_STARTED"}'
    )
    (project / "state" / "review_findings.json").write_text('{"items":[]}')
    (project / "knowledge" / "SKILLS_INDEX.md").write_text(
        "# SKILLS_INDEX.md\n\nPopulated by KnowledgeLearningAgent.\n"
    )
    return project


@pytest.fixture
def config(tmp_project: Path) -> Config:
    cfg = Config.load(tmp_project)
    cfg.dry_run = True
    return cfg
