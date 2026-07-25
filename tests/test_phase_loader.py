"""Tests for phase and dependency loading."""

from agent_system.config import Config
from agent_system.phase_loader import PhaseLoader


def test_loads_all_phases(config: Config):
    loader = PhaseLoader(config)
    phases = loader.get_all_phases()
    assert len(phases) >= 25


def test_bootstrap_has_no_dependencies(config: Config):
    loader = PhaseLoader(config)
    bootstrap = loader.get_phase("BOOTSTRAP")
    assert bootstrap is not None
    assert bootstrap.dependencies == []


def test_phase_0a_depends_on_bootstrap(config: Config):
    loader = PhaseLoader(config)
    phase = loader.get_phase("0A")
    assert phase is not None
    assert "BOOTSTRAP" in phase.dependencies


def test_dependency_validation(config: Config):
    loader = PhaseLoader(config)
    errors = loader.validate_dependencies()
    assert len(errors) == 0


def test_eligible_phases_empty_start(config: Config):
    loader = PhaseLoader(config)
    eligible = loader.get_eligible_phases(set())
    non_final = [p for p in eligible if p.phase_id != "FINAL"]
    assert len(non_final) == 1
    assert non_final[0].phase_id == "BOOTSTRAP"


def test_eligible_after_bootstrap(config: Config):
    loader = PhaseLoader(config)
    eligible = loader.get_eligible_phases({"BOOTSTRAP"})
    non_final = [p for p in eligible if p.phase_id != "FINAL"]
    assert len(non_final) == 1
    assert non_final[0].phase_id == "0A"


def test_eligible_after_0a(config: Config):
    loader = PhaseLoader(config)
    eligible = loader.get_eligible_phases({"BOOTSTRAP", "0A"})
    ids = [p.phase_id for p in eligible]
    assert "0" in ids


def test_next_phase_ordering(config: Config):
    loader = PhaseLoader(config)
    next_p = loader.get_next_phase(set())
    assert next_p is not None
    assert next_p.phase_id == "BOOTSTRAP"

    next_p = loader.get_next_phase({"BOOTSTRAP"})
    assert next_p is not None
    assert next_p.phase_id == "0A"


def test_parallel_eligible_phases(config: Config):
    loader = PhaseLoader(config)
    completed = {"BOOTSTRAP", "0A", "0", "1"}
    eligible = loader.get_eligible_phases(completed)
    ids = {p.phase_id for p in eligible}
    assert "2" in ids
    assert "4" in ids
