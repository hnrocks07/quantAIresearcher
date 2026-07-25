"""Skill evolution tracker — records what each agent learned and improved over time.

Every skill improvement is documented with: what changed, why, evidence of
improvement, and which phase/task triggered it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .config import Config
from .models import _now, _uid

logger = logging.getLogger(__name__)


class SkillImprovement:

    def __init__(
        self,
        improvement_id: str = "",
        agent_role: str = "",
        phase_id: str = "",
        task_id: str = "",
        run_id: str = "",
        skill_name: str = "",
        category: str = "",
        before: str = "",
        after: str = "",
        reason: str = "",
        evidence: str = "",
        impact: str = "",
        timestamp: str = "",
    ) -> None:
        self.improvement_id = improvement_id or _uid()
        self.agent_role = agent_role
        self.phase_id = phase_id
        self.task_id = task_id
        self.run_id = run_id
        self.skill_name = skill_name
        self.category = category
        self.before = before
        self.after = after
        self.reason = reason
        self.evidence = evidence
        self.impact = impact
        self.timestamp = timestamp or _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "improvement_id": self.improvement_id,
            "agent_role": self.agent_role,
            "phase_id": self.phase_id,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "skill_name": self.skill_name,
            "category": self.category,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
            "evidence": self.evidence,
            "impact": self.impact,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SkillImprovement:
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__init__.__code__.co_varnames})


class SkillTracker:

    def __init__(self, config: Config) -> None:
        self.config = config
        self._dir = config.knowledge_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._dir / "skill_improvements.jsonl"
        self._summary_path = self._dir / "SKILL_EVOLUTION.md"
        self._agent_skills_path = self._dir / "agent_skills.json"

    def _load_agent_skills(self) -> dict[str, Any]:
        if self._agent_skills_path.exists():
            with open(self._agent_skills_path) as f:
                return json.load(f)
        return {"agents": {}}

    def _save_agent_skills(self, data: dict[str, Any]) -> None:
        with open(self._agent_skills_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def record_improvement(self, improvement: SkillImprovement) -> None:
        with open(self._log_path, "a") as f:
            f.write(json.dumps(improvement.to_dict(), default=str) + "\n")

        skills = self._load_agent_skills()
        agent = improvement.agent_role
        if agent not in skills["agents"]:
            skills["agents"][agent] = {"skills": {}, "improvement_count": 0}

        agent_data = skills["agents"][agent]
        skill = improvement.skill_name

        if skill not in agent_data["skills"]:
            agent_data["skills"][skill] = {
                "current_level": improvement.after,
                "history": [],
                "learned_in_phase": improvement.phase_id,
                "improvement_count": 0,
            }

        skill_data = agent_data["skills"][skill]
        skill_data["history"].append({
            "improvement_id": improvement.improvement_id,
            "before": improvement.before,
            "after": improvement.after,
            "reason": improvement.reason,
            "phase_id": improvement.phase_id,
            "timestamp": improvement.timestamp,
        })
        skill_data["current_level"] = improvement.after
        skill_data["improvement_count"] = len(skill_data["history"])
        agent_data["improvement_count"] += 1

        self._save_agent_skills(skills)
        self._update_evolution_doc()

        logger.info("Skill improvement recorded: %s / %s -> %s [%s]",
                     agent, skill, improvement.after, improvement.reason)

    def record_from_review(
        self,
        agent_role: str,
        phase_id: str,
        task_id: str,
        run_id: str,
        finding_category: str,
        finding_title: str,
        remediation_description: str,
    ) -> None:
        self.record_improvement(SkillImprovement(
            agent_role=agent_role,
            phase_id=phase_id,
            task_id=task_id,
            run_id=run_id,
            skill_name=f"review_lesson_{finding_category}",
            category="review_remediation",
            before="issue detected by ReviewerAgent",
            after="remediation applied, pattern learned",
            reason=finding_title,
            evidence=remediation_description,
            impact="Reduces recurrence of similar findings in future tasks",
        ))

    def record_from_failure(
        self,
        agent_role: str,
        phase_id: str,
        task_id: str,
        run_id: str,
        failure_description: str,
        recovery_description: str,
    ) -> None:
        self.record_improvement(SkillImprovement(
            agent_role=agent_role,
            phase_id=phase_id,
            task_id=task_id,
            run_id=run_id,
            skill_name="failure_recovery",
            category="failure_learning",
            before=failure_description,
            after=recovery_description,
            reason="Task failure triggered learning",
            evidence=f"Failure: {failure_description}; Recovery: {recovery_description}",
            impact="Improves resilience and reduces retry rate",
        ))

    def record_from_knowledge_reuse(
        self,
        agent_role: str,
        phase_id: str,
        task_id: str,
        run_id: str,
        knowledge_entry_id: str,
        reuse_description: str,
    ) -> None:
        self.record_improvement(SkillImprovement(
            agent_role=agent_role,
            phase_id=phase_id,
            task_id=task_id,
            run_id=run_id,
            skill_name="knowledge_application",
            category="knowledge_reuse",
            before="knowledge available but unused",
            after="knowledge applied to current task",
            reason=f"Reused knowledge entry {knowledge_entry_id}",
            evidence=reuse_description,
            impact="Demonstrates cross-phase learning",
        ))

    def get_agent_skills(self, agent_role: str) -> dict[str, Any]:
        skills = self._load_agent_skills()
        return skills.get("agents", {}).get(agent_role, {"skills": {}, "improvement_count": 0})

    def get_all_improvements(self) -> list[SkillImprovement]:
        if not self._log_path.exists():
            return []
        results = []
        with open(self._log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(SkillImprovement.from_dict(json.loads(line)))
        return results

    def get_improvements_by_phase(self, phase_id: str) -> list[SkillImprovement]:
        return [i for i in self.get_all_improvements() if i.phase_id == phase_id]

    def get_improvement_summary(self) -> dict[str, Any]:
        skills = self._load_agent_skills()
        summary: dict[str, Any] = {
            "total_improvements": 0,
            "by_agent": {},
            "by_category": {},
            "by_phase": {},
        }

        for agent, data in skills.get("agents", {}).items():
            count = data.get("improvement_count", 0)
            summary["total_improvements"] += count
            summary["by_agent"][agent] = {
                "improvement_count": count,
                "skills_count": len(data.get("skills", {})),
                "skill_names": list(data.get("skills", {}).keys()),
            }

        for imp in self.get_all_improvements():
            cat = imp.category
            summary["by_category"][cat] = summary["by_category"].get(cat, 0) + 1
            pid = imp.phase_id
            summary["by_phase"][pid] = summary["by_phase"].get(pid, 0) + 1

        return summary

    def _update_evolution_doc(self) -> None:
        skills = self._load_agent_skills()
        lines = [
            "# Skill Evolution Log",
            "",
            "Auto-generated. Tracks what each agent learned and improved over time.",
            "",
        ]

        for agent in sorted(skills.get("agents", {}).keys()):
            data = skills["agents"][agent]
            lines.append(f"## {agent}")
            lines.append(f"Total improvements: {data.get('improvement_count', 0)}")
            lines.append("")

            for skill_name in sorted(data.get("skills", {}).keys()):
                skill = data["skills"][skill_name]
                lines.append(f"### {skill_name}")
                lines.append(f"Current level: {skill.get('current_level', 'unknown')}")
                lines.append(f"Learned in phase: {skill.get('learned_in_phase', 'unknown')}")
                lines.append(f"Improvements: {skill.get('improvement_count', 0)}")
                lines.append("")

                for h in skill.get("history", []):
                    lines.append(f"- Phase {h.get('phase_id', '?')}: "
                                  f"{h.get('before', '?')} -> {h.get('after', '?')} "
                                  f"({h.get('reason', '')})")

                lines.append("")

        with open(self._summary_path, "w") as f:
            f.write("\n".join(lines) + "\n")
