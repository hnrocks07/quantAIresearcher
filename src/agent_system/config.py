"""System configuration and constants."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@dataclass
class Config:
    project_root: Path = field(default_factory=_project_root)
    max_concurrent_agents: int = 2
    max_task_retries: int = 3
    review_remediation_max_cycles: int = 2
    real_money_trading: bool = False
    dry_run: bool = False
    model: str = "claude"
    anthropic_api_key: str = ""

    @property
    def state_dir(self) -> Path:
        return self.project_root / "state"

    @property
    def knowledge_dir(self) -> Path:
        return self.project_root / "knowledge"

    @property
    def phases_dir(self) -> Path:
        return self.project_root / "phases"

    @property
    def agents_dir(self) -> Path:
        return self.project_root / "agents"

    @property
    def logs_dir(self) -> Path:
        return self.project_root / "logs"

    @property
    def telemetry_dir(self) -> Path:
        return self.project_root / "telemetry"

    @property
    def artifacts_dir(self) -> Path:
        return self.project_root / "artifacts"

    @property
    def evidence_dir(self) -> Path:
        return self.project_root / "evidence"

    def ensure_dirs(self) -> None:
        for d in [self.state_dir, self.knowledge_dir, self.logs_dir,
                   self.telemetry_dir, self.artifacts_dir, self.evidence_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, project_root: Path | None = None) -> Config:
        root = project_root or _project_root()
        config_path = root / "state" / "project_config.json"
        cfg = cls(project_root=root)
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
            cfg.max_concurrent_agents = data.get("max_concurrent_llm_agents", 2)
            cfg.real_money_trading = data.get("real_money_trading", False)
            cfg.model = data.get("model", "claude")
        cfg.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        cfg.ensure_dirs()
        return cfg

    @property
    def has_api_key(self) -> bool:
        return bool(self.anthropic_api_key)
