"""Tests for all 6 agent implementations."""

from agent_system.agents import AGENT_REGISTRY
from agent_system.config import Config
from agent_system.models import Task, AgentRole


def test_all_agents_registered():
    assert len(AGENT_REGISTRY) == 6
    expected = {
        "EngineeringManagerAgent",
        "PlannerAgent",
        "ResearchAgent",
        "SeniorEngineerAgent",
        "ReviewerAgent",
        "KnowledgeLearningAgent",
    }
    assert set(AGENT_REGISTRY.keys()) == expected


def test_engineering_manager_dry_run(config: Config):
    config.dry_run = True
    agent = AGENT_REGISTRY["EngineeringManagerAgent"](config)
    task = Task(title="Test task", phase_id="P1")
    result = agent.run(task, {})

    assert result["action"] == "delegate"
    assert "delegation_plan" in result
    assert result["acceptance_criteria_verified"] is True
    assert "_meta" in result
    assert result["_meta"]["dry_run"] is True


def test_planner_dry_run(config: Config):
    config.dry_run = True
    agent = AGENT_REGISTRY["PlannerAgent"](config)
    task = Task(title="Plan phase", phase_id="P1")
    result = agent.run(task, {})

    assert result["action"] == "plan"
    assert len(result["tasks"]) > 0
    for t in result["tasks"]:
        assert "task_id" in t
        assert "title" in t
        assert "acceptance_criteria" in t


def test_researcher_dry_run(config: Config):
    config.dry_run = True
    agent = AGENT_REGISTRY["ResearchAgent"](config)
    task = Task(title="Research topic", phase_id="P1")
    result = agent.run(task, {})

    assert result["action"] == "research"
    assert len(result["findings"]) > 0
    finding = result["findings"][0]
    assert finding["access_controls_respected"] is True


def test_senior_engineer_dry_run(config: Config):
    config.dry_run = True
    agent = AGENT_REGISTRY["SeniorEngineerAgent"](config)
    task = Task(title="Implement feature", phase_id="P1")
    result = agent.run(task, {})

    assert result["action"] == "implement"
    assert result["tests_passed"] is True
    assert result["secrets_in_code"] is False
    assert result["real_trading_disabled"] is True


def test_senior_engineer_remediation(config: Config):
    config.dry_run = True
    agent = AGENT_REGISTRY["SeniorEngineerAgent"](config)
    task = Task(title="Fix issue", phase_id="P1")
    context = {"review_findings": [{"finding_id": "f1", "title": "Bug"}]}
    result = agent.run(task, context)

    assert result["action"] == "remediate"
    assert result["remediation_applied"] is True
    assert "f1" in result["findings_addressed"]


def test_reviewer_dry_run(config: Config):
    config.dry_run = True
    agent = AGENT_REGISTRY["ReviewerAgent"](config)
    task = Task(title="Review code", phase_id="P1")
    result = agent.run(task, {})

    assert result["action"] == "review"
    assert "findings" in result
    assert result["evidence_integrity_check"]["no_fabricated_telemetry"] is True


def test_reviewer_re_review(config: Config):
    config.dry_run = True
    agent = AGENT_REGISTRY["ReviewerAgent"](config)
    task = Task(title="Re-review", phase_id="P1")
    context = {"review_findings": [{"finding_id": "f1"}]}
    result = agent.run(task, context)

    assert result["action"] == "re_review"
    assert result["recommendation"] == "APPROVED"


def test_knowledge_learning_dry_run(config: Config):
    config.dry_run = True
    agent = AGENT_REGISTRY["KnowledgeLearningAgent"](config)
    task = Task(title="Learn", phase_id="P1")
    result = agent.run(task, {})

    assert result["action"] == "learn"
    assert result["knowledge_stored"] > 0
    assert result["skills_index_updated"] is True


def test_all_agents_have_system_prompts(config: Config):
    config.dry_run = True
    for name, cls in AGENT_REGISTRY.items():
        agent = cls(config)
        assert agent.system_prompt, f"{name} missing system_prompt"
        assert agent.role in AgentRole, f"{name} has invalid role"


def test_all_agents_produce_meta(config: Config):
    config.dry_run = True
    task = Task(title="Meta test", phase_id="P1")
    for name, cls in AGENT_REGISTRY.items():
        agent = cls(config)
        result = agent.run(task, {})
        assert "_meta" in result, f"{name} missing _meta"
        assert result["_meta"]["agent"] == name
        assert result["_meta"]["dry_run"] is True
