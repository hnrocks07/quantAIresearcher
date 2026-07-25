# Agent System Architecture

## Overview

The autonomous engineering agent system coordinates six specialized AI agents through a structured workflow pipeline. Each agent uses Claude as the underlying LLM and operates within a persistent state framework that survives restarts.

## Agent Roles

| Agent | Responsibility |
|---|---|
| EngineeringManagerAgent | Roadmap ownership, delegation, acceptance, resource management, evidence enforcement |
| PlannerAgent | Phase decomposition into testable tasks with dependencies, criteria, and risks |
| ResearchAgent | Uncertainty resolution using authoritative sources, provenance tracking |
| SeniorEngineerAgent | Incremental implementation with tests, migrations, docs; no self-approval |
| ReviewerAgent | Independent review across correctness, security, data, evidence; BLOCKER/HIGH/MEDIUM/LOW |
| KnowledgeLearningAgent | Lessons, failures, patterns, skills capture; tracks retrieval and reuse evidence |

## Workflow Pipeline

Manager evaluates -> Planner decomposes -> Research (if needed) -> Engineer implements -> tests -> Reviewer classifies findings -> remediation loop for BLOCKER/HIGH -> retest -> Knowledge capture -> state update -> next eligible phase.

## Key Components

| Component | File | Purpose |
|---|---|---|
| Orchestrator | src/agent_system/orchestrator.py | Main engine coordinating the pipeline |
| State Manager | src/agent_system/state_manager.py | JSON-based persistence with atomic writes |
| Telemetry | src/agent_system/telemetry.py | Evidence capture with MEASURED/DERIVED/ESTIMATED/UNAVAILABLE |
| Phase Loader | src/agent_system/phase_loader.py | Loads 26 phases from ROADMAP.md with dependency resolution |
| Resource Manager | src/agent_system/resource_manager.py | Concurrency limits (max 2 LLM agents) |
| Knowledge Store | src/agent_system/knowledge_store.py | Stores and retrieves lessons, updates SKILLS_INDEX |
| CLI | src/agent_system/cli.py | Commands: dry-run, run, status, resume, validate |

## Persistence

All state is stored as JSON under state/ with atomic writes (write-to-temp + rename). Files:
- current_run.json: Active run ID and status
- current_phase.json: Current phase and status
- phases.json: All phase states
- tasks.json: All task states
- review_findings.json: Review findings with severity
- checkpoint.json: Resume checkpoint

## Telemetry Schema

Every event records: run_id, phase_id, task_id, agent_role, event_type, timestamp, duration, status, metric_type, model_identifier, token_usage, cost, artifacts, handoffs, human interventions, knowledge events.

Token usage and cost are classified UNAVAILABLE when running without API integration and MEASURED when API responses include them.

## Skill Evolution and Continuous Improvement

The system tracks what each agent learns and improves over time via the SkillTracker (src/agent_system/skill_tracker.py).

Improvement sources:
- Review findings: When ReviewerAgent identifies issues and SeniorEngineerAgent remediates, the pattern is recorded as a learned skill
- Failure recovery: When a task fails and is recovered, the failure-to-recovery path is captured
- Knowledge reuse: When knowledge from a previous phase is applied to a current task, the reuse event is recorded
- Knowledge capture: Every lesson stored by KnowledgeLearningAgent is tracked as a skill improvement

Storage:
- knowledge/agent_skills.json: Per-agent skill registry with current level and full history
- knowledge/skill_improvements.jsonl: Append-only log of every improvement event
- knowledge/SKILL_EVOLUTION.md: Auto-generated human-readable evolution document

Each improvement records: agent, phase, task, run, skill name, category, before state, after state, reason, evidence, and impact.

The SKILL_EVOLUTION.md shows progressive improvement over time, documenting exactly what changed, why, and which phase triggered it. This feeds directly into the case study's "evidence of learning across phases" requirement.

## Resource Constraints

Designed for MacBook Air M3, 8 cores, 16GB:
- Max 2 concurrent LLM agents (semaphore-enforced)
- Backtest workers capped at 3
- Optimization workers capped at 2
- Heavy jobs queued/throttled

## Safety Rules

- Never commit or log secrets
- Never enable real-money trading
- Generated/imported code must be sandboxed
- Human approval required for: credentials, destructive actions, paid services, licensing, architecture changes, anything enabling real trading
