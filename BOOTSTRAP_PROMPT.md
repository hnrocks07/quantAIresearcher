# BOOTSTRAP_PROMPT.md

You are the Bootstrap Architect. Build the autonomous engineering-agent system FIRST. Do NOT begin Phase 0A or Phase 0 yet.

Read PROJECT_CONTEXT.md, ROADMAP.md, AGENT_ARCHITECTURE.md, all files under agents/, phases/, state/, and knowledge/. Inspect the repository and treat it as greenfield unless actual code exists.

Use Claude as the ONLY underlying LLM.

Create six logical agents:
EngineeringManagerAgent, PlannerAgent, ResearchAgent, SeniorEngineerAgent, ReviewerAgent, KnowledgeLearningAgent.

Implement:
- persistent state across restarts
- phase/dependency loader
- task lifecycle
- bounded retries/failure handling
- review/remediation loop
- knowledge retrieval and reusable skill capture
- structured local orchestration logs
- resource/concurrency guardrails
- safe resume/continue
- dry-run mode

Workflow:
Manager -> Planner -> Research when needed -> Engineer -> tests -> Reviewer -> remediation for BLOCKER/HIGH -> retest -> KnowledgeLearning -> state update -> next eligible phase.

Maximum concurrent LLM agents: 2. Keep orchestration lightweight for MacBook Air M3/16GB.

Human approval only for credentials, irreversible destructive actions, paid services, licensing/legal decisions, consequential architecture changes, or anything that could enable real-money trading.

Never commit/log secrets. Never run untrusted/generated code unrestricted. Never enable real-money trading.

Dry-run a synthetic phase and verify delegation, state persistence/resume, bounded retries, review feedback, knowledge storage/retrieval, resource limits and local logs.

Deliver orchestration implementation, tests, README.md, AGENT_SYSTEM_ARCHITECTURE.md, HOW_TO_RUN.md, HOW_TO_RESUME.md, SECURITY.md, KNOWN_LIMITATIONS.md.

Only report `AGENT SYSTEM READY` after critical tests and dry-run pass. STOP before Phase 0 and give the exact single instruction to start the project.

ADDITIONAL PRIMARY OBJECTIVE:
The project must prove, with auditable evidence, whether this specialized agent team using the configured tracked Claude model can build a production-grade AI application.

During bootstrap itself, begin capturing orchestration evidence where possible. Design the agent system so all future runs have stable run/phase/task IDs and telemetry hooks for model identity, timing, handoffs, tests, reviews, retries, remediation, human interventions, artifacts, and usage/cost when actually exposed.

Never fabricate telemetry.

After bootstrap validation, the first product-roadmap phase is Phase 0A: Agent Engineering Measurement & Evidence Framework. Do not skip it.
