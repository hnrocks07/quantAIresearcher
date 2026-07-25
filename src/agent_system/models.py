"""Core data models for the agent system."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return uuid.uuid4().hex[:12]


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    REMEDIATION = "REMEDIATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class PhaseStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PLANNING = "PLANNING"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class Severity(str, Enum):
    BLOCKER = "BLOCKER"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class MetricType(str, Enum):
    MEASURED = "MEASURED"
    DERIVED = "DERIVED"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"


class AgentRole(str, Enum):
    ENGINEERING_MANAGER = "EngineeringManagerAgent"
    PLANNER = "PlannerAgent"
    RESEARCHER = "ResearchAgent"
    SENIOR_ENGINEER = "SeniorEngineerAgent"
    REVIEWER = "ReviewerAgent"
    KNOWLEDGE_LEARNING = "KnowledgeLearningAgent"


class HumanInterventionCategory(str, Enum):
    APPROVAL = "APPROVAL"
    CORRECTION = "CORRECTION"
    CLARIFICATION = "CLARIFICATION"
    OVERRIDE = "OVERRIDE"
    ESCALATION = "ESCALATION"
    CONFIGURATION = "CONFIGURATION"
    REJECTION = "REJECTION"


@dataclass
class Task:
    task_id: str = field(default_factory=_uid)
    phase_id: str = ""
    run_id: str = ""
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: str = ""
    dependencies: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    test_results: dict[str, Any] = field(default_factory=dict)
    retries: int = 0
    max_retries: int = 3
    created_at: str = field(default_factory=_now)
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    review_findings: list[dict] = field(default_factory=list)
    remediation_cycles: int = 0
    human_intervention_required: bool = False
    human_intervention_reason: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        data = dict(data)
        if "status" in data:
            data["status"] = TaskStatus(data["status"])
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class Phase:
    phase_id: str = ""
    name: str = ""
    status: PhaseStatus = PhaseStatus.NOT_STARTED
    dependencies: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    run_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    acceptance_outcome: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Phase:
        data = dict(data)
        if "status" in data:
            data["status"] = PhaseStatus(data["status"])
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class ReviewFinding:
    finding_id: str = field(default_factory=_uid)
    task_id: str = ""
    phase_id: str = ""
    run_id: str = ""
    reviewer: str = AgentRole.REVIEWER.value
    category: str = ""
    severity: Severity = Severity.MEDIUM
    title: str = ""
    description: str = ""
    file_path: str = ""
    recommendation: str = ""
    status: str = "OPEN"
    remediation_agent: str = ""
    remediation_description: str = ""
    remediated_at: str = ""
    verified: bool = False
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> ReviewFinding:
        data = dict(data)
        if "severity" in data:
            data["severity"] = Severity(data["severity"])
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class TelemetryEvent:
    event_id: str = field(default_factory=_uid)
    run_id: str = ""
    phase_id: str = ""
    task_id: str = ""
    agent_role: str = ""
    event_type: str = ""
    timestamp: str = field(default_factory=_now)
    duration_seconds: float = 0.0
    status: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    metric_type: MetricType = MetricType.MEASURED
    model_identifier: str = ""
    token_usage: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    handoff_from: str = ""
    handoff_to: str = ""
    human_intervention: bool = False
    human_intervention_reason: str = ""
    knowledge_retrieved: list[str] = field(default_factory=list)
    knowledge_stored: list[str] = field(default_factory=list)
    error: str = ""
    retries: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["metric_type"] = self.metric_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> TelemetryEvent:
        data = dict(data)
        if "metric_type" in data:
            data["metric_type"] = MetricType(data["metric_type"])
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class AgentHandoff:
    from_agent: str = ""
    to_agent: str = ""
    task_id: str = ""
    phase_id: str = ""
    run_id: str = ""
    timestamp: str = field(default_factory=_now)
    context_summary: str = ""
    artifacts_passed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class KnowledgeEntry:
    entry_id: str = field(default_factory=_uid)
    phase_id: str = ""
    task_id: str = ""
    category: str = ""
    title: str = ""
    content: str = ""
    tags: list[str] = field(default_factory=list)
    source_agent: str = ""
    created_at: str = field(default_factory=_now)
    retrieval_count: int = 0
    last_retrieved: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeEntry:
        data = dict(data)
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class HumanIntervention:
    intervention_id: str = field(default_factory=_uid)
    run_id: str = ""
    phase_id: str = ""
    task_id: str = ""
    category: HumanInterventionCategory = HumanInterventionCategory.APPROVAL
    agent_role: str = ""
    reason: str = ""
    decision: str = ""
    impact: str = ""
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["category"] = self.category.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> HumanIntervention:
        data = dict(data)
        if "category" in data:
            data["category"] = HumanInterventionCategory(data["category"])
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class AgentDecision:
    decision_id: str = field(default_factory=_uid)
    run_id: str = ""
    phase_id: str = ""
    task_id: str = ""
    agent_role: str = ""
    decision_type: str = ""
    decision: str = ""
    alternatives: list[str] = field(default_factory=list)
    rationale: str = ""
    confidence: str = ""
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AgentDecision:
        data = dict(data)
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class TestExecution:
    execution_id: str = field(default_factory=_uid)
    run_id: str = ""
    phase_id: str = ""
    task_id: str = ""
    test_name: str = ""
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    coverage_pct: float = -1.0
    metric_type: MetricType = MetricType.MEASURED
    timestamp: str = field(default_factory=_now)

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors

    def to_dict(self) -> dict:
        d = asdict(self)
        d["metric_type"] = self.metric_type.value
        d["total"] = self.total
        return d

    @classmethod
    def from_dict(cls, data: dict) -> TestExecution:
        data = dict(data)
        data.pop("total", None)
        if "metric_type" in data:
            data["metric_type"] = MetricType(data["metric_type"])
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class PhaseMetrics:
    phase_id: str = ""
    run_id: str = ""
    task_count: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_duration_seconds: float = 0.0
    remediation_cycles: int = 0
    findings_count: int = 0
    findings_blocker: int = 0
    findings_high: int = 0
    knowledge_entries_created: int = 0
    knowledge_reuse_count: int = 0
    human_intervention_count: int = 0
    agent_decision_count: int = 0
    test_pass_count: int = 0
    test_fail_count: int = 0
    metric_type: MetricType = MetricType.DERIVED
    computed_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["metric_type"] = self.metric_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> PhaseMetrics:
        data = dict(data)
        if "metric_type" in data:
            data["metric_type"] = MetricType(data["metric_type"])
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class KnowledgeReuseEvent:
    event_id: str = field(default_factory=_uid)
    run_id: str = ""
    phase_id: str = ""
    task_id: str = ""
    agent_role: str = ""
    knowledge_entry_id: str = ""
    knowledge_title: str = ""
    source_phase: str = ""
    application: str = ""
    outcome: str = ""
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeReuseEvent:
        data = dict(data)
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})
