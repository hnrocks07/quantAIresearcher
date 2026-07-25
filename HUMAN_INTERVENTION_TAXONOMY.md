# Human Intervention Taxonomy

Classifies every instance where a human must intervene in the autonomous agent workflow. Each intervention is recorded as a structured HumanIntervention entity with its category, reason, decision, and impact.


## Categories

### 1. APPROVAL
The agent system requests explicit human sign-off before proceeding.

When it applies:
- Phase acceptance (human confirms phase deliverables meet requirements)
- Promotion of AI-generated or imported strategies to candidate status
- Any action involving paid services, external APIs, or credentials
- Architecture changes that alter the system's fundamental structure
- Enabling real-money trading features (permanently out of initial scope)

Severity implication: Normal workflow. Expected at defined checkpoints. Does not indicate agent failure.

Example: "Phase 0A deliverables ready for acceptance review."


### 2. CORRECTION
The human corrects an agent's output, approach, or implementation.

When it applies:
- Agent produced incorrect code that passed review
- Agent chose a suboptimal approach that doesn't meet requirements
- Agent misinterpreted task requirements
- Agent applied wrong knowledge or pattern to current context

Severity implication: Indicates a gap in agent capability. Tracked to measure improvement over time — declining correction rate signals learning.

Example: "Engineer used synchronous file writes instead of atomic writes as specified."


### 3. CLARIFICATION
The agent cannot proceed due to ambiguous or incomplete requirements and asks for human input.

When it applies:
- Task description is ambiguous
- Acceptance criteria are contradictory
- Multiple valid approaches exist and the choice is domain-dependent
- External context is needed that agents cannot access

Severity implication: Normal for early phases. High clarification rate later may indicate poor task decomposition by PlannerAgent.

Example: "Should the backtest engine support tick-level data or only OHLCV?"


### 4. OVERRIDE
The human overrides an agent's decision or system constraint.

When it applies:
- Human disagrees with ReviewerAgent's verdict and forces acceptance
- Human overrides resource limits (e.g., temporarily allows more concurrent agents)
- Human skips a blocked dependency that the orchestrator enforces
- Human changes priority/ordering of tasks against the plan

Severity implication: Should be rare. Frequent overrides suggest the agent system's judgment is miscalibrated.

Example: "Override: accepting task despite reviewer BLOCKER finding — finding is a false positive."


### 5. ESCALATION
An agent encounters a situation beyond its capability and escalates to human.

When it applies:
- Task requires access to external systems the agent cannot reach
- Security-sensitive operation needs human authorization
- Agent has exhausted retries and cannot recover
- Error condition the agent doesn't know how to diagnose

Severity implication: Expected for system-boundary operations. Excessive escalation for routine tasks indicates agent limitations.

Example: "Cannot access production database credentials — requires human to configure SSH tunnel."


### 6. CONFIGURATION
Human provides or changes system configuration that agents cannot self-configure.

When it applies:
- Setting API keys or credentials (ANTHROPIC_API_KEY, database passwords)
- Configuring environment-specific settings (ports, paths, resource limits)
- Installing system dependencies (PostgreSQL, Python packages)
- Setting up external integrations (TradingView API, broker connections)

Severity implication: Normal, especially in early phases. Configuration interventions should decrease after initial setup.

Example: "Human configured ANTHROPIC_API_KEY for live API execution."


### 7. REJECTION
The human rejects an agent's output entirely and requests a fundamentally different approach.

When it applies:
- Agent's entire approach is wrong (not just implementation details)
- Deliverable does not match what was requested
- Agent went off-scope or exceeded boundaries
- Quality is below minimum acceptable threshold

Severity implication: Significant agent failure. Should be very rare — indicates breakdown in planning or task understanding.

Example: "Reject: the planner decomposed the phase into 50 micro-tasks instead of 5 meaningful deliverables."


## Recording Rules

1. Every intervention MUST be recorded with its category, regardless of severity
2. The reason field must explain WHY the intervention was needed, not just WHAT happened
3. The decision field records the human's actual decision or action
4. The impact field records how the intervention changed the task/phase outcome
5. Interventions are append-only — never delete or modify historical records
6. If an intervention doesn't fit any category, use CORRECTION as default and note in reason


## Metrics Derived from Interventions

- human_intervention_rate = tasks with any intervention / total tasks
- autonomous_completion_rate = tasks completed without intervention / total tasks
- intervention_category_distribution = count per category
- phase_intervention_trend = intervention rate per phase (should decrease over time)
- correction_decline_rate = correction interventions per phase (measures learning)


## Case Study Evidence

The intervention taxonomy feeds directly into the final case study:
- "Can AI agents build production software autonomously?" -> answered by autonomous_completion_rate
- "Where do AI agents still need humans?" -> answered by category distribution
- "Do AI agents learn and improve?" -> answered by correction_decline_rate across phases
