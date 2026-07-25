"""Phase and dependency loader from ROADMAP.md and phase files."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from .config import Config
from .models import Phase, PhaseStatus

logger = logging.getLogger(__name__)

ROADMAP_PHASES = [
    {"phase_id": "BOOTSTRAP", "name": "Autonomous Engineering Agent System",
     "dependencies": []},
    {"phase_id": "0A",
     "name": "Agent Engineering Measurement & Evidence Framework",
     "dependencies": ["BOOTSTRAP"]},
    {"phase_id": "0",
     "name": "Greenfield Architecture & Local Foundation Design",
     "dependencies": ["0A"]},
    {"phase_id": "1", "name": "Fresh App Skeleton & Local PostgreSQL",
     "dependencies": ["0"]},
    {"phase_id": "2",
     "name": "Local Data, Logging, Audit & Backup Foundation",
     "dependencies": ["1"]},
    {"phase_id": "3", "name": "Market Data Foundation",
     "dependencies": ["2"]},
    {"phase_id": "4", "name": "Strategy Registry & Provenance",
     "dependencies": ["1"]},
    {"phase_id": "5", "name": "Reproducible Backtesting Engine",
     "dependencies": ["3", "4"]},
    {"phase_id": "6", "name": "TradingView/Pine Manual Import",
     "dependencies": ["4", "5"]},
    {"phase_id": "7",
     "name": "TradingView Automatic Discovery & Eligible Import",
     "dependencies": ["4", "6"]},
    {"phase_id": "8",
     "name": "Pine Compatibility & TradingView Parity Validation",
     "dependencies": ["5", "6"]},
    {"phase_id": "9", "name": "Leaderboard & Research Dashboard v1",
     "dependencies": ["5"]},
    {"phase_id": "10",
     "name": "Vectorized Research Worker & Resource Scheduler",
     "dependencies": ["5"]},
    {"phase_id": "11", "name": "Optimization & Robustness Engine",
     "dependencies": ["8", "10"]},
    {"phase_id": "12", "name": "Position Sizing & Risk Engine",
     "dependencies": ["5"]},
    {"phase_id": "13", "name": "Portfolio Research Engine",
     "dependencies": ["5", "12"]},
    {"phase_id": "14",
     "name": "Weakness Detection & Strategy Diagnostics",
     "dependencies": ["11"]},
    {"phase_id": "15",
     "name": "AI Strategy Research & Improvement Loop",
     "dependencies": ["6", "8", "14"]},
    {"phase_id": "16",
     "name": "Custom Strategy Agent / On-Demand Backtest",
     "dependencies": ["5", "6"]},
    {"phase_id": "17", "name": "Paper Trading & Historical Replay",
     "dependencies": ["3", "4", "12"]},
    {"phase_id": "18",
     "name": "Live Data Simulation & Strategy Monitoring",
     "dependencies": ["17"]},
    {"phase_id": "19", "name": "Notifications & Reports",
     "dependencies": ["2"]},
    {"phase_id": "20", "name": "Experiment Tracking & Research Audit",
     "dependencies": ["5"]},
    {"phase_id": "21", "name": "Market Calendar & Event Engine",
     "dependencies": ["3"]},
    {"phase_id": "22", "name": "Corporate Actions & Adjusted Data",
     "dependencies": ["3"]},
    {"phase_id": "FINAL",
     "name": "End-to-End Validation & Release Candidate",
     "dependencies": ["REQUIRED_PHASES"]},
]


class PhaseLoader:

    def __init__(self, config: Config) -> None:
        self.config = config
        self._phases: dict[str, Phase] = {}
        self._load_phases()

    def _load_phases(self) -> None:
        for p in ROADMAP_PHASES:
            self._phases[p["phase_id"]] = Phase(
                phase_id=p["phase_id"],
                name=p["name"],
                dependencies=p["dependencies"],
            )
        logger.info("Loaded %d phases from roadmap", len(self._phases))

    def get_phase(self, phase_id: str) -> Phase | None:
        return self._phases.get(phase_id)

    def get_all_phases(self) -> dict[str, Phase]:
        return dict(self._phases)

    def get_eligible_phases(
        self, completed_phases: set[str]
    ) -> list[Phase]:
        eligible = []
        for pid, phase in self._phases.items():
            if pid in completed_phases:
                continue
            deps_met = all(d in completed_phases for d in phase.dependencies
                           if d != "REQUIRED_PHASES")
            if deps_met:
                eligible.append(phase)
        return eligible

    def get_next_phase(self, completed_phases: set[str]) -> Phase | None:
        eligible = self.get_eligible_phases(completed_phases)
        if not eligible:
            return None
        order = [p["phase_id"] for p in ROADMAP_PHASES]
        eligible.sort(key=lambda p: order.index(p.phase_id)
                       if p.phase_id in order else 999)
        return eligible[0]

    def load_phase_spec(self, phase_id: str) -> str:
        phase_file = self.config.phases_dir / f"phase_{phase_id.zfill(2)}.md"
        if not phase_file.exists():
            phase_file = self.config.phases_dir / f"phase_{phase_id}.md"
        if phase_file.exists():
            return phase_file.read_text()
        return ""

    def validate_dependencies(self) -> list[str]:
        errors = []
        all_ids = set(self._phases.keys())
        for pid, phase in self._phases.items():
            for dep in phase.dependencies:
                if dep not in all_ids and dep != "REQUIRED_PHASES":
                    errors.append(
                        f"Phase {pid} depends on unknown phase {dep}")
        return errors
