# FIRST_PROMPT.md

Read `BOOTSTRAP_PROMPT.md` and execute it as the governing bootstrap instruction.

Also read `PROJECT_CONTEXT.md`, `ROADMAP.md`, `AGENT_ARCHITECTURE.md`, every agent definition under `agents/`, every phase specification under `phases/`, current state under `state/`, and existing knowledge under `knowledge/`.

Important:
- This is a BRAND-NEW application. Do not assume or stabilize a legacy MVP.
- Build and validate the autonomous engineering-agent system FIRST.
- Use Claude as the only underlying model for all logical agents.
- Do not start Phase 0A or Phase 0 until the agent-system dry run and critical tests pass.
- Keep core platform data local by default: PostgreSQL for structured system-of-record data and local artifact/log/backup storage where appropriate.
- TradingView/Pine strategy intake must support BOTH manual import and automatic discovery/import of eligible, authorized, accessible strategies.
- Never bypass protected/private/invite-only sources, access controls, licensing restrictions, paywalls, or technical protections.
- Preserve strategy provenance/source/license metadata and clearly classify source/compatibility/parity status.
- Advanced custom charting is FUTURE SCOPE. Do not build a TradingView clone now.
- Do not enable real-money trading.
- Do not ask me for broker/API credentials until a specific integration actually requires them.

When the autonomous agent system is fully validated, stop before Phase 0, report `AGENT SYSTEM READY`, summarize dry-run/test results, and give me the exact single instruction to start the project.

- This project has TWO primary deliverables: the production-grade AI Quant application AND an auditable proof/case study of how effectively the specialized agent team built it.
- Preserve prospective evidence from the beginning. Track agent runs, tasks, handoffs, tests, reviews, remediation, failures, human interventions, artifacts, model identity and usage/cost when actually available.
- Never fabricate unavailable telemetry; label measured/derived/estimated/unavailable values.
- After bootstrap, Phase 0A (Agent Engineering Measurement & Evidence Framework) must run before Phase 0.
