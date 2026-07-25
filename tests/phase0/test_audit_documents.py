"""Tests for Phase 0 audit document completeness."""

import os
import re

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS_DIR = os.path.join(REPO_ROOT, "docs", "phase0")


def repo_path(filename: str) -> str:
    return os.path.join(REPO_ROOT, filename)


def doc_path(filename: str) -> str:
    return os.path.join(DOCS_DIR, filename)


def read_file(path: str) -> str:
    assert os.path.exists(path), f"Required file missing: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestSourceFilesExist:

    def test_project_context_exists(self):
        assert os.path.exists(repo_path("PROJECT_CONTEXT.md"))

    def test_roadmap_exists(self):
        assert os.path.exists(repo_path("ROADMAP.md"))


class TestProjectContextFields:

    def setup_method(self):
        self.content = read_file(repo_path("PROJECT_CONTEXT.md"))

    REQUIRED_FIELDS = [
        "project_name", "version", "language", "storage",
        "real_trading", "secrets_policy", "scope_phase0",
        "out_of_scope_phase0", "target_environment",
    ]

    def test_all_required_fields_present(self):
        for field in self.REQUIRED_FIELDS:
            assert field in self.content, f"Missing: {field}"

    def test_real_trading_is_false(self):
        assert "false" in self.content.lower()

    def test_storage_is_local_sqlite(self):
        assert "sqlite" in self.content.lower()

    def test_secrets_policy_no_source(self):
        content_lower = self.content.lower()
        assert "env" in content_lower and "secret" in content_lower

    def test_advanced_charting_out_of_scope(self):
        assert "chart" in self.content.lower() or "visualization" in self.content.lower()


class TestRoadmapFields:

    def setup_method(self):
        self.content = read_file(repo_path("ROADMAP.md"))

    def test_phase_0_present(self):
        assert "Phase 0" in self.content

    def test_all_deliverable_ids_present(self):
        for d in ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]:
            assert d in self.content

    def test_gate_conditions_present(self):
        assert "gate" in self.content.lower()

    def test_future_phases_marked_future(self):
        assert "FUTURE" in self.content


class TestContextAuditSummary:

    def setup_method(self):
        self.content = read_file(doc_path("context_audit_summary.md"))

    def test_file_exists(self):
        assert os.path.exists(doc_path("context_audit_summary.md"))

    def test_contains_confirmed_fields(self):
        assert self.content.count("CONFIRMED") >= 6

    def test_no_pending_fields(self):
        assert "PENDING" not in self.content

    def test_scope_documented(self):
        assert "Scope" in self.content

    def test_out_of_scope_documented(self):
        assert "Out of Scope" in self.content

    def test_real_trading_confirmed(self):
        content_lower = self.content.lower()
        assert "real_trading" in content_lower or "real trading" in content_lower
        assert "false" in content_lower or "disabled" in content_lower

    def test_local_first_confirmed(self):
        assert "local" in self.content.lower()

    def test_secrets_confirmed(self):
        assert "secret" in self.content.lower() or "Env" in self.content

    def test_deliverables_mapped(self):
        for d in ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]:
            assert d in self.content

    def test_no_fabricated_date(self):
        assert "2025-01-01" not in self.content


class TestOpenQuestions:

    def setup_method(self):
        self.content = read_file(doc_path("open_questions.md"))

    def test_file_exists(self):
        assert os.path.exists(doc_path("open_questions.md"))

    def test_has_resolved_section(self):
        assert "Resolved" in self.content

    def test_has_deferred_section(self):
        assert "Deferred" in self.content

    def test_sqlite_decision_documented(self):
        assert "SQLite" in self.content

    def test_no_fabricated_date(self):
        assert "2025-01-01" not in self.content


class TestDeliverablesChecklist:

    def setup_method(self):
        self.content = read_file(doc_path("phase0_deliverables_checklist.md"))

    def test_file_exists(self):
        assert os.path.exists(doc_path("phase0_deliverables_checklist.md"))

    def test_all_deliverables_present(self):
        for d in ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]:
            assert d in self.content

    def test_all_complete(self):
        assert self.content.count("COMPLETE") >= 7

    def test_gate_conditions_present(self):
        assert "Gate" in self.content

    def test_no_fabricated_date(self):
        assert "2025-01-01" not in self.content
