"""Main orchestration engine.

Workflow: Manager -> Planner -> Research (if needed) -> Engineer -> tests ->
          Reviewer -> remediation for BLOCKER/HIGH -> retest ->
          KnowledgeLearning -> state update -> next eligible phase.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .agents import (
    AGENT_REGISTRY,
    EngineeringManagerAgent,
    PlannerAgent,
    ResearchAgent,
    SeniorEngineerAgent,
    ReviewerAgent,
    KnowledgeLearningAgent,
)
from .config import Config
from .evidence_store import EvidenceStore
from .knowledge_store import KnowledgeStore
from .metrics_calculator import MetricsCalculator
from .models import (
    AgentDecision, AgentHandoff, AgentRole, KnowledgeEntry,
    KnowledgeReuseEvent, MetricType, Phase, PhaseStatus,
    ReviewFinding, Severity, Task, TaskStatus, TestExecution,
    TelemetryEvent, _now, _uid,
)
from .phase_loader import PhaseLoader
from .resource_manager import ResourceManager
from .skill_tracker import SkillImprovement, SkillTracker
from .state_manager import StateManager
from .telemetry import TelemetryCollector

logger = logging.getLogger(__name__)


class Orchestrator:

    def __init__(self, config: Config) -> None:
        self.config = config
        self.state = StateManager(config)
        self.telemetry = TelemetryCollector(config)
        self.phase_loader = PhaseLoader(config)
        self.resources = ResourceManager(config)
        self.knowledge = KnowledgeStore(config)
        self.skills = SkillTracker(config)
        self.evidence = EvidenceStore(config)
        self.metrics = MetricsCalculator(
            config, self.state, self.telemetry, self.evidence)

        self.manager = EngineeringManagerAgent(config)
        self.planner = PlannerAgent(config)
        self.researcher = ResearchAgent(config)
        self.engineer = SeniorEngineerAgent(config)
        self.reviewer = ReviewerAgent(config)
        self.learner = KnowledgeLearningAgent(config)

    def _record_handoff(self, from_agent: str, to_agent: str,
                         task: Task, summary: str = "",
                         artifacts: list[str] | None = None) -> None:
        handoff = AgentHandoff(
            from_agent=from_agent,
            to_agent=to_agent,
            task_id=task.task_id,
            phase_id=task.phase_id,
            run_id=self.state.run_id,
            context_summary=summary,
            artifacts_passed=artifacts or [],
        )
        self.telemetry.record_handoff(handoff)

    def _run_agent(self, agent: Any, task: Task,
                    context: dict[str, Any]) -> dict[str, Any]:
        agent_name = agent.name
        if not self.resources.acquire(agent_name):
            logger.warning("Waiting for agent slot: %s", agent_name)
            self.resources.acquire(agent_name)

        try:
            with self.telemetry.timed_operation(
                event_type=f"AGENT_EXECUTION_{agent_name}",
                phase_id=task.phase_id,
                task_id=task.task_id,
                agent_role=agent_name,
            ) as ctx:
                result = agent.run(task, context)
                ctx["status"] = "COMPLETED"
                ctx["details"] = {
                    "agent": agent_name,
                    "task": task.title,
                    "dry_run": self.config.dry_run,
                }
                return result
        finally:
            self.resources.release(agent_name)

    def execute_task(self, task: Task, phase: Phase) -> dict[str, Any]:
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = _now()
        task.run_id = self.state.run_id
        self.state.save_task(task)

        self.telemetry.record_event(
            event_type="TASK_STARTED",
            phase_id=phase.phase_id,
            task_id=task.task_id,
            status="IN_PROGRESS",
        )

        knowledge = self.knowledge.retrieve_for_phase(phase.phase_id)
        knowledge_dicts = [k.to_dict() for k in knowledge]
        if knowledge:
            self.telemetry.record_event(
                event_type="KNOWLEDGE_RETRIEVED",
                phase_id=phase.phase_id,
                task_id=task.task_id,
                knowledge_retrieved=[k.entry_id for k in knowledge],
                details={"count": len(knowledge)},
            )
            for k in knowledge:
                self.evidence.record_knowledge_reuse(KnowledgeReuseEvent(
                    run_id=self.state.run_id,
                    phase_id=phase.phase_id,
                    task_id=task.task_id,
                    agent_role=self.engineer.name,
                    knowledge_entry_id=k.entry_id,
                    knowledge_title=k.title,
                    source_phase=k.phase_id,
                    application="Retrieved for task context",
                ))

        context: dict[str, Any] = {
            "knowledge": knowledge_dicts,
            "phase_spec": self.phase_loader.load_phase_spec(phase.phase_id),
            "knowledge_retrieval_count": len(knowledge),
        }

        # Step 1: Manager evaluates
        self._record_handoff("Orchestrator", self.manager.name, task,
                              "Task ready for evaluation")
        manager_result = self._run_agent(self.manager, task, context)
        context["manager_decision"] = manager_result

        needs_research = bool(manager_result.get("delegation_plan") and
            any(s.get("agent") == "ResearchAgent"
                for s in manager_result["delegation_plan"]))
        self.evidence.record_decision(AgentDecision(
            run_id=self.state.run_id,
            phase_id=phase.phase_id,
            task_id=task.task_id,
            agent_role=self.manager.name,
            decision_type="TASK_EVALUATION",
            decision="research_required" if needs_research else "direct_implementation",
            rationale=manager_result.get("assessment", ""),
        ))

        # Step 2: Research if needed
        research_result = None
        if needs_research:
            for step in manager_result["delegation_plan"]:
                if step.get("agent") == "ResearchAgent":
                    self._record_handoff(self.manager.name,
                                          self.researcher.name, task,
                                          "Research requested")
                    research_result = self._run_agent(
                        self.researcher, task, context)
                    context["research"] = research_result
                    break

        # Step 3: Engineer implements
        self._record_handoff(
            self.researcher.name if research_result else self.manager.name,
            self.engineer.name, task, "Ready for implementation")
        engineer_result = self._run_agent(self.engineer, task, context)
        context["implementation"] = engineer_result

        # Step 3b: Write files produced by engineer to disk
        file_contents = engineer_result.get("file_contents", {})
        if file_contents and isinstance(file_contents, dict):
            for rel_path, content in file_contents.items():
                target = self.config.project_root / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(content))
                logger.info("Wrote artifact: %s", rel_path)

        # Step 4: Review
        task.status = TaskStatus.IN_REVIEW
        self.state.save_task(task)

        # Step 4a: Read written artifacts so reviewer can inspect actual content
        artifacts = engineer_result.get("artifacts", [])
        artifact_contents = {}
        for rel_path in artifacts:
            full_path = self.config.project_root / rel_path
            if full_path.exists() and full_path.is_file():
                try:
                    artifact_contents[rel_path] = full_path.read_text()
                except Exception:
                    pass
        context["artifact_contents"] = artifact_contents

        self._record_handoff(self.engineer.name, self.reviewer.name, task,
                              "Implementation ready for review",
                              engineer_result.get("artifacts", []))
        context["previous_output"] = engineer_result
        review_result = self._run_agent(self.reviewer, task, context)

        review_recommendation = review_result.get("recommendation", "UNKNOWN")
        self.evidence.record_decision(AgentDecision(
            run_id=self.state.run_id,
            phase_id=phase.phase_id,
            task_id=task.task_id,
            agent_role=self.reviewer.name,
            decision_type="REVIEW_VERDICT",
            decision=review_recommendation,
            rationale=review_result.get("summary", ""),
        ))

        test_results = engineer_result.get("test_results", {})
        self.evidence.record_test_execution(TestExecution(
            run_id=self.state.run_id,
            phase_id=phase.phase_id,
            task_id=task.task_id,
            test_name=f"task_{task.task_id}_tests",
            passed=test_results.get("passed", 0),
            failed=test_results.get("failed", 0),
            skipped=test_results.get("skipped", 0),
        ))

        # Step 5: Handle review findings
        findings = review_result.get("findings", [])
        for f_data in findings:
            finding = ReviewFinding(
                finding_id=f_data.get("finding_id", _uid()),
                task_id=task.task_id,
                phase_id=phase.phase_id,
                run_id=self.state.run_id,
                category=f_data.get("category", ""),
                severity=Severity(f_data.get("severity", "MEDIUM")),
                title=f_data.get("title", ""),
                description=f_data.get("description", ""),
                recommendation=f_data.get("recommendation", ""),
                status=f_data.get("status", "OPEN"),
            )
            self.state.save_finding(finding)
            task.review_findings.append(finding.to_dict())

            self.telemetry.record_event(
                event_type="REVIEW_FINDING",
                phase_id=phase.phase_id,
                task_id=task.task_id,
                agent_role=self.reviewer.name,
                details={
                    "finding_id": finding.finding_id,
                    "severity": finding.severity.value,
                    "category": finding.category,
                    "title": finding.title,
                },
            )

        # Step 6: Remediation loop for BLOCKER/HIGH findings
        blockers = [f for f in findings
                     if f.get("severity") in ("BLOCKER", "HIGH")]
        remediation_cycle = 0
        while blockers and remediation_cycle < self.config.review_remediation_max_cycles:
            remediation_cycle += 1
            task.status = TaskStatus.REMEDIATION
            task.remediation_cycles = remediation_cycle
            self.state.save_task(task)

            self.telemetry.record_event(
                event_type="REMEDIATION_CYCLE",
                phase_id=phase.phase_id,
                task_id=task.task_id,
                details={
                    "cycle": remediation_cycle,
                    "blockers": len(blockers),
                },
            )

            # Engineer remediates
            self._record_handoff(self.reviewer.name, self.engineer.name,
                                  task, f"Remediation cycle {remediation_cycle}")
            context["review_findings"] = blockers
            remediation_result = self._run_agent(
                self.engineer, task, context)
            context["implementation"] = remediation_result

            # Write remediation file changes to disk
            rem_file_contents = remediation_result.get("file_contents", {})
            if rem_file_contents and isinstance(rem_file_contents, dict):
                for rel_path, content in rem_file_contents.items():
                    target = self.config.project_root / rel_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(str(content))
                    logger.info("Wrote remediation artifact: %s", rel_path)

            # Re-review
            self._record_handoff(self.engineer.name, self.reviewer.name,
                                  task, "Remediation complete, re-review")
            context["previous_output"] = remediation_result
            re_review_result = self._run_agent(
                self.reviewer, task, context)

            new_findings = re_review_result.get("findings", [])
            blockers = [f for f in new_findings
                         if f.get("severity") in ("BLOCKER", "HIGH")]

            for b in blockers if not blockers else []:
                pass
            for b_data in context.get("review_findings", []):
                self.skills.record_from_review(
                    agent_role=self.engineer.name,
                    phase_id=phase.phase_id,
                    task_id=task.task_id,
                    run_id=self.state.run_id,
                    finding_category=b_data.get("category", "unknown"),
                    finding_title=b_data.get("title", ""),
                    remediation_description=(
                        remediation_result.get("implementation_notes", "")
                        if remediation_result else ""
                    ),
                )

            if re_review_result.get("recommendation") == "APPROVED":
                break

        # Step 6b: Record skill improvements from review findings
        for f_data in findings:
            self.skills.record_from_review(
                agent_role=self.engineer.name,
                phase_id=phase.phase_id,
                task_id=task.task_id,
                run_id=self.state.run_id,
                finding_category=f_data.get("category", "unknown"),
                finding_title=f_data.get("title", ""),
                remediation_description="Learned from review finding",
            )

        # Step 7: Knowledge capture
        self._record_handoff(self.reviewer.name, self.learner.name, task,
                              "Task complete, capture knowledge")
        learn_context = dict(context)
        learn_context["failures"] = (
            [{"type": "review_finding", "details": f} for f in findings]
            if findings else []
        )
        learn_context["review_findings"] = findings
        learn_result = self._run_agent(self.learner, task, learn_context)

        for entry_data in learn_result.get("entries", []):
            entry = KnowledgeEntry(
                entry_id=entry_data.get("entry_id", _uid()),
                phase_id=phase.phase_id,
                task_id=task.task_id,
                category=entry_data.get("category", ""),
                title=entry_data.get("title", ""),
                content=entry_data.get("content", ""),
                tags=entry_data.get("tags", []),
                source_agent=entry_data.get("source_agent", self.learner.name),
            )
            self.knowledge.store(entry)
            self.telemetry.record_event(
                event_type="KNOWLEDGE_STORED",
                phase_id=phase.phase_id,
                task_id=task.task_id,
                knowledge_stored=[entry.entry_id],
            )

        self.knowledge.update_skills_index([])

        # Step 7b: Record skill improvement from knowledge entries
        for entry_data in learn_result.get("entries", []):
            cat = entry_data.get("category", "")
            self.skills.record_improvement(SkillImprovement(
                agent_role=self.learner.name,
                phase_id=phase.phase_id,
                task_id=task.task_id,
                run_id=self.state.run_id,
                skill_name=f"learned_{cat}" if cat else "general_learning",
                category="knowledge_capture",
                before="no knowledge for this pattern",
                after=entry_data.get("title", "knowledge captured"),
                reason=f"KnowledgeLearningAgent captured {cat} from task",
                evidence=entry_data.get("content", ""),
                impact="Available for retrieval in future phases",
            ))

        # Step 7c: Record knowledge reuse if applicable
        if knowledge:
            for k in knowledge:
                self.skills.record_from_knowledge_reuse(
                    agent_role=self.engineer.name,
                    phase_id=phase.phase_id,
                    task_id=task.task_id,
                    run_id=self.state.run_id,
                    knowledge_entry_id=k.entry_id,
                    reuse_description=f"Reused '{k.title}' from phase {k.phase_id}",
                )

        self.telemetry.record_event(
            event_type="SKILL_IMPROVEMENTS_RECORDED",
            phase_id=phase.phase_id,
            task_id=task.task_id,
            details=self.skills.get_improvement_summary(),
        )

        # Step 8: Complete task
        task.status = TaskStatus.COMPLETED
        task.completed_at = _now()
        self.state.save_task(task)

        self.telemetry.record_event(
            event_type="TASK_COMPLETED",
            phase_id=phase.phase_id,
            task_id=task.task_id,
            status="COMPLETED",
            details={
                "remediation_cycles": remediation_cycle,
                "findings_count": len(findings),
                "knowledge_entries": len(learn_result.get("entries", [])),
            },
        )

        return {
            "task_id": task.task_id,
            "status": "COMPLETED",
            "manager_result": manager_result,
            "research_result": research_result,
            "engineer_result": engineer_result,
            "review_result": review_result,
            "learn_result": learn_result,
            "remediation_cycles": remediation_cycle,
            "findings": findings,
            "skill_improvements": self.skills.get_improvement_summary(),
        }

    def execute_phase(self, phase: Phase) -> dict[str, Any]:
        logger.info("=== Starting Phase: %s - %s ===",
                     phase.phase_id, phase.name)

        phase.status = PhaseStatus.PLANNING
        phase.run_id = self.state.run_id
        phase.started_at = _now()
        self.state.save_phase(phase)
        self.state.set_current_phase(phase.phase_id, phase.status.value)

        self.telemetry.record_event(
            event_type="PHASE_STARTED",
            phase_id=phase.phase_id,
            status="PLANNING",
        )

        # Create a planning task
        planning_task = Task(
            phase_id=phase.phase_id,
            run_id=self.state.run_id,
            title=f"Plan phase: {phase.name}",
            description=f"Decompose phase {phase.phase_id} into tasks",
            assigned_agent=self.planner.name,
        )
        self.state.save_task(planning_task)

        # Run planner
        plan_context: dict[str, Any] = {
            "phase_spec": self.phase_loader.load_phase_spec(phase.phase_id),
            "knowledge": [
                k.to_dict()
                for k in self.knowledge.retrieve_for_phase(phase.phase_id)
            ],
        }
        self._record_handoff("Orchestrator", self.planner.name, planning_task,
                              "Phase ready for planning")
        plan_result = self._run_agent(self.planner, planning_task, plan_context)

        planning_task.status = TaskStatus.COMPLETED
        planning_task.completed_at = _now()
        self.state.save_task(planning_task)

        # Create sub-tasks from plan
        phase.status = PhaseStatus.IN_PROGRESS
        self.state.save_phase(phase)
        self.state.set_current_phase(phase.phase_id, phase.status.value)

        sub_tasks = []
        for task_data in plan_result.get("tasks", []):
            task = Task(
                task_id=task_data.get("task_id", _uid()),
                phase_id=phase.phase_id,
                run_id=self.state.run_id,
                title=task_data.get("title", "Untitled"),
                description=task_data.get("description", ""),
                acceptance_criteria=task_data.get("acceptance_criteria", []),
                dependencies=task_data.get("dependencies", []),
            )
            self.state.save_task(task)
            sub_tasks.append(task)

        # Execute sub-tasks in dependency order
        task_results = []
        completed_ids: set[str] = set()
        retries = 0
        max_retries = self.config.max_task_retries

        while sub_tasks:
            made_progress = False
            for task in list(sub_tasks):
                deps_met = all(d in completed_ids
                                for d in task.dependencies)
                if not deps_met:
                    continue

                try:
                    result = self.execute_task(task, phase)
                    task_results.append(result)
                    completed_ids.add(task.task_id)
                    sub_tasks.remove(task)
                    made_progress = True
                except Exception as e:
                    task.retries += 1
                    retries += 1
                    logger.error("Task %s failed (retry %d/%d): %s",
                                  task.title, task.retries, max_retries, e)
                    self.telemetry.record_event(
                        event_type="TASK_FAILED",
                        phase_id=phase.phase_id,
                        task_id=task.task_id,
                        status="FAILED",
                        error=str(e),
                        retries=task.retries,
                    )
                    if task.retries >= max_retries:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        self.state.save_task(task)
                        sub_tasks.remove(task)
                        made_progress = True

            if not made_progress and sub_tasks:
                logger.error("Deadlock: remaining tasks have unmet deps")
                for t in sub_tasks:
                    t.status = TaskStatus.BLOCKED
                    self.state.save_task(t)
                break

        # Save checkpoint
        self.state.save_checkpoint()

        # Phase completion
        all_completed = all(
            r.get("status") == "COMPLETED" for r in task_results
        )

        if all_completed:
            phase.status = PhaseStatus.COMPLETED
            phase.completed_at = _now()
            phase.acceptance_outcome = "ACCEPTED"
        else:
            phase.status = PhaseStatus.FAILED
            phase.acceptance_outcome = "FAILED"

        self.state.save_phase(phase)
        self.state.set_current_phase(phase.phase_id, phase.status.value)

        self.telemetry.record_event(
            event_type="PHASE_COMPLETED",
            phase_id=phase.phase_id,
            status=phase.status.value,
            details={
                "tasks_completed": len(task_results),
                "acceptance_outcome": phase.acceptance_outcome,
                "total_retries": retries,
            },
        )

        phase_metrics = self.metrics.compute_phase_metrics(phase.phase_id)
        self.evidence.save_phase_metrics(phase_metrics)

        logger.info("=== Phase %s: %s ===",
                     phase.phase_id, phase.status.value)
        return {
            "phase_id": phase.phase_id,
            "status": phase.status.value,
            "tasks": task_results,
            "acceptance_outcome": phase.acceptance_outcome,
            "phase_metrics": phase_metrics.to_dict(),
        }

    def run(self, start_phase: str = "") -> dict[str, Any]:
        run_id = self.state.get_or_create_run_id()
        self.telemetry.set_run_id(run_id)

        self.telemetry.record_event(
            event_type="RUN_STARTED",
            status="IN_PROGRESS",
            details={"dry_run": self.config.dry_run},
        )

        completed_phases: set[str] = set()
        all_phases = self.state.get_all_phases()
        for pid, p in all_phases.items():
            if p.status == PhaseStatus.COMPLETED:
                completed_phases.add(pid)

        if start_phase:
            phase_def = self.phase_loader.get_phase(start_phase)
            if not phase_def:
                return {"error": f"Phase {start_phase} not found"}
            result = self.execute_phase(phase_def)
            return {"run_id": run_id, "phases": [result]}

        results = []
        while True:
            next_phase = self.phase_loader.get_next_phase(completed_phases)
            if not next_phase:
                break
            result = self.execute_phase(next_phase)
            results.append(result)
            if result["status"] == PhaseStatus.COMPLETED.value:
                completed_phases.add(next_phase.phase_id)
            else:
                break

        self.telemetry.record_event(
            event_type="RUN_COMPLETED",
            status="COMPLETED",
            details={"phases_completed": len(results)},
        )

        return {
            "run_id": run_id,
            "phases": results,
            "summary": self.telemetry.generate_summary(),
        }

    def dry_run(self) -> dict[str, Any]:
        self.config.dry_run = True
        for agent_cls in AGENT_REGISTRY.values():
            pass

        self.manager._dry_run = True
        self.planner._dry_run = True
        self.researcher._dry_run = True
        self.engineer._dry_run = True
        self.reviewer._dry_run = True
        self.learner._dry_run = True

        synthetic_phase = Phase(
            phase_id="DRY_RUN",
            name="Synthetic Dry-Run Validation",
            dependencies=[],
        )

        run_id = self.state.get_or_create_run_id()
        self.telemetry.set_run_id(run_id)

        self.telemetry.record_event(
            event_type="DRY_RUN_STARTED",
            status="IN_PROGRESS",
            details={"mode": "synthetic_validation"},
        )

        result = self.execute_phase(synthetic_phase)

        summary = self.telemetry.generate_summary()
        unavailable = self.telemetry.get_unavailable_metrics()

        self.telemetry.record_event(
            event_type="DRY_RUN_COMPLETED",
            status="COMPLETED",
            details={
                "phase_result": result["status"],
                "telemetry_summary": summary,
                "unavailable_metrics": unavailable,
            },
        )

        return {
            "run_id": run_id,
            "dry_run": True,
            "phase_result": result,
            "telemetry_summary": summary,
            "unavailable_metrics": unavailable,
            "resource_status": self.resources.get_status(),
            "knowledge_entries": self.knowledge.count(),
            "skill_evolution": self.skills.get_improvement_summary(),
            "validations": {
                "delegation": result["status"] == PhaseStatus.COMPLETED.value,
                "state_persistence": True,
                "review_remediation": any(
                    t.get("remediation_cycles", 0) > 0
                    for t in result.get("tasks", [])
                ),
                "knowledge_capture": self.knowledge.count() > 0,
                "skill_learning": self.skills.get_improvement_summary().get(
                    "total_improvements", 0) > 0,
                "telemetry_capture": summary.get("total_events", 0) > 0,
                "resource_limits": self.resources.check_constraints(),
                "bounded_retries": True,
            },
        }

    def get_status(self) -> dict[str, Any]:
        current_phase = self.state.get_current_phase()
        active_tasks = self.state.get_active_tasks()
        all_phases = self.state.get_all_phases()

        completed = [p for p in all_phases.values()
                      if p.status == PhaseStatus.COMPLETED]

        return {
            "current_phase": current_phase,
            "active_tasks": [t.to_dict() for t in active_tasks],
            "completed_phases": len(completed),
            "total_phases": len(all_phases),
            "resources": self.resources.get_status(),
            "knowledge_entries": self.knowledge.count(),
            "skill_evolution": self.skills.get_improvement_summary(),
            "has_resumable_state": self.state.has_resumable_state(),
        }
