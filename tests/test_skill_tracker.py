"""Tests for skill evolution tracking."""

from agent_system.config import Config
from agent_system.orchestrator import Orchestrator
from agent_system.skill_tracker import SkillImprovement, SkillTracker


def test_record_improvement(config: Config):
    st = SkillTracker(config)
    st.record_improvement(SkillImprovement(
        agent_role="SeniorEngineerAgent",
        phase_id="P1",
        task_id="T1",
        skill_name="error_handling",
        category="review_remediation",
        before="missing edge-case handling",
        after="comprehensive error handling added",
        reason="ReviewerAgent found missing checks",
        evidence="Test added for boundary conditions",
        impact="Fewer review findings on error handling",
    ))

    skills = st.get_agent_skills("SeniorEngineerAgent")
    assert skills["improvement_count"] == 1
    assert "error_handling" in skills["skills"]
    assert skills["skills"]["error_handling"]["current_level"] == (
        "comprehensive error handling added"
    )


def test_record_from_review(config: Config):
    st = SkillTracker(config)
    st.record_from_review(
        agent_role="SeniorEngineerAgent",
        phase_id="P1",
        task_id="T1",
        run_id="run_1",
        finding_category="testing",
        finding_title="Missing boundary tests",
        remediation_description="Added 5 boundary tests",
    )

    improvements = st.get_all_improvements()
    assert len(improvements) == 1
    assert improvements[0].category == "review_remediation"


def test_record_from_failure(config: Config):
    st = SkillTracker(config)
    st.record_from_failure(
        agent_role="SeniorEngineerAgent",
        phase_id="P2",
        task_id="T2",
        run_id="run_1",
        failure_description="Task crashed on large input",
        recovery_description="Added input size validation",
    )

    improvements = st.get_all_improvements()
    assert len(improvements) == 1
    assert improvements[0].category == "failure_learning"


def test_record_from_knowledge_reuse(config: Config):
    st = SkillTracker(config)
    st.record_from_knowledge_reuse(
        agent_role="SeniorEngineerAgent",
        phase_id="P3",
        task_id="T3",
        run_id="run_1",
        knowledge_entry_id="k1",
        reuse_description="Reused error handling pattern from P1",
    )

    improvements = st.get_all_improvements()
    assert len(improvements) == 1
    assert improvements[0].category == "knowledge_reuse"


def test_improvement_summary(config: Config):
    st = SkillTracker(config)
    st.record_from_review(
        "Agent1", "P1", "T1", "run_1", "testing", "Fix1", "Done1")
    st.record_from_review(
        "Agent1", "P2", "T2", "run_1", "security", "Fix2", "Done2")
    st.record_from_failure(
        "Agent2", "P1", "T3", "run_1", "Crash", "Fixed")

    summary = st.get_improvement_summary()
    assert summary["total_improvements"] == 3
    assert "Agent1" in summary["by_agent"]
    assert summary["by_agent"]["Agent1"]["improvement_count"] == 2
    assert "review_remediation" in summary["by_category"]
    assert "failure_learning" in summary["by_category"]


def test_improvements_by_phase(config: Config):
    st = SkillTracker(config)
    st.record_from_review(
        "Agent1", "P1", "T1", "run_1", "cat1", "F1", "D1")
    st.record_from_review(
        "Agent1", "P2", "T2", "run_1", "cat2", "F2", "D2")

    p1_improvements = st.get_improvements_by_phase("P1")
    assert len(p1_improvements) == 1
    assert p1_improvements[0].phase_id == "P1"


def test_evolution_doc_generated(config: Config):
    st = SkillTracker(config)
    st.record_improvement(SkillImprovement(
        agent_role="TestAgent",
        phase_id="P1",
        skill_name="test_skill",
        category="test",
        before="v1",
        after="v2",
        reason="improved",
    ))

    doc_path = config.knowledge_dir / "SKILL_EVOLUTION.md"
    assert doc_path.exists()
    content = doc_path.read_text()
    assert "TestAgent" in content
    assert "test_skill" in content
    assert "v1" in content
    assert "v2" in content


def test_skill_history_accumulates(config: Config):
    st = SkillTracker(config)
    st.record_improvement(SkillImprovement(
        agent_role="Agent1", phase_id="P1", skill_name="coding",
        before="basic", after="intermediate", reason="Phase 1 learning"))
    st.record_improvement(SkillImprovement(
        agent_role="Agent1", phase_id="P2", skill_name="coding",
        before="intermediate", after="advanced", reason="Phase 2 learning"))

    skills = st.get_agent_skills("Agent1")
    assert skills["skills"]["coding"]["current_level"] == "advanced"
    assert skills["skills"]["coding"]["improvement_count"] == 2
    assert len(skills["skills"]["coding"]["history"]) == 2


def test_dry_run_captures_skill_improvements(config: Config):
    orch = Orchestrator(config)
    result = orch.dry_run()

    assert "skill_evolution" in result
    assert result["skill_evolution"]["total_improvements"] > 0
    assert result["validations"]["skill_learning"] is True


def test_persistence_across_instances(config: Config):
    st1 = SkillTracker(config)
    st1.record_from_review(
        "Agent1", "P1", "T1", "run_1", "cat1", "Fix", "Done")

    st2 = SkillTracker(config)
    improvements = st2.get_all_improvements()
    assert len(improvements) == 1

    skills = st2.get_agent_skills("Agent1")
    assert skills["improvement_count"] == 1
