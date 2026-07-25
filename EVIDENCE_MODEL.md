# Evidence Model

Defines the schema for all evidence entities tracked by the agent system. Every entity has stable IDs linking phase -> task -> agent run -> artifact -> test -> review -> remediation.


## Existing Entities (from Bootstrap)

### 1. TelemetryEvent
File: telemetry/events_{run_id}.jsonl (append-only JSONL)
Source: src/agent_system/models.py

| Field | Type | Description |
|---|---|---|
| event_id | str | Unique ID (auto-generated) |
| run_id | str | Links to the execution run |
| phase_id | str | Links to phase |
| task_id | str | Links to task |
| agent_role | str | Which agent produced this event |
| event_type | str | E.g., TASK_STARTED, PHASE_COMPLETED, AGENT_HANDOFF |
| timestamp | str | ISO 8601 UTC |
| duration_seconds | float | Measured wall-clock time |
| status | str | IN_PROGRESS, COMPLETED, FAILED |
| details | dict | Event-specific structured data |
| metric_type | MetricType | MEASURED / DERIVED / ESTIMATED / UNAVAILABLE |
| model_identifier | str | Claude model ID from API response |
| token_usage | dict | Input/output tokens from API |
| cost | dict | Computed cost from token usage |
| artifacts | list[str] | References to produced artifacts |
| handoff_from | str | Source agent (for AGENT_HANDOFF events) |
| handoff_to | str | Target agent (for AGENT_HANDOFF events) |
| human_intervention | bool | Whether human intervened |
| human_intervention_reason | str | Free-text reason |
| knowledge_retrieved | list[str] | IDs of knowledge entries retrieved |
| knowledge_stored | list[str] | IDs of knowledge entries stored |
| error | str | Error message if failed |
| retries | int | Retry count |


### 2. Task
File: state/tasks.json (atomic write)
Source: src/agent_system/models.py

| Field | Type | Description |
|---|---|---|
| task_id | str | Unique ID |
| phase_id | str | Links to phase |
| run_id | str | Links to run |
| title | str | Task description |
| description | str | Detailed requirements |
| status | TaskStatus | PENDING / IN_PROGRESS / IN_REVIEW / REMEDIATION / COMPLETED / FAILED / BLOCKED / SKIPPED |
| assigned_agent | str | Agent role assigned |
| dependencies | list[str] | Task IDs that must complete first |
| acceptance_criteria | list[str] | What "done" means |
| artifacts | list[str] | Produced artifact references |
| tests | list[str] | Test names |
| test_results | dict | Test outcome summary |
| retries | int | Current retry count |
| max_retries | int | Maximum retries allowed |
| review_findings | list[dict] | Findings from ReviewerAgent |
| remediation_cycles | int | Number of remediation loops |
| human_intervention_required | bool | Whether human was needed |
| human_intervention_reason | str | Why human was needed |
| created_at / started_at / completed_at | str | Lifecycle timestamps |
| error | str | Error if failed |


### 3. Phase
File: state/phases.json (atomic write)
Source: src/agent_system/models.py

| Field | Type | Description |
|---|---|---|
| phase_id | str | Unique ID (e.g., BOOTSTRAP, 0A, 0) |
| name | str | Human-readable name |
| status | PhaseStatus | NOT_STARTED / PLANNING / IN_PROGRESS / IN_REVIEW / COMPLETED / FAILED / BLOCKED |
| dependencies | list[str] | Phase IDs that must complete first |
| tasks | list[str] | Task IDs in this phase |
| run_id | str | Links to run |
| started_at / completed_at | str | Lifecycle timestamps |
| acceptance_outcome | str | ACCEPTED / FAILED |


### 4. ReviewFinding
File: state/review_findings.json (atomic write)
Source: src/agent_system/models.py

| Field | Type | Description |
|---|---|---|
| finding_id | str | Unique ID |
| task_id | str | Links to task |
| phase_id | str | Links to phase |
| run_id | str | Links to run |
| reviewer | str | Always ReviewerAgent |
| category | str | Finding category |
| severity | Severity | BLOCKER / HIGH / MEDIUM / LOW / INFO |
| title | str | Finding title |
| description | str | Detailed description |
| file_path | str | Affected file |
| recommendation | str | Suggested fix |
| status | str | OPEN / FIXED / WONT_FIX |
| remediation_agent | str | Agent that fixed it |
| remediation_description | str | How it was fixed |
| remediated_at | str | When fixed |
| verified | bool | Whether fix was verified |
| created_at | str | When found |


### 5. AgentHandoff
Source: src/agent_system/models.py (recorded via TelemetryCollector)

| Field | Type | Description |
|---|---|---|
| from_agent | str | Source agent |
| to_agent | str | Target agent |
| task_id | str | Links to task |
| phase_id | str | Links to phase |
| run_id | str | Links to run |
| timestamp | str | When handoff occurred |
| context_summary | str | What context was passed |
| artifacts_passed | list[str] | Artifact references |


### 6. KnowledgeEntry
File: knowledge/{entry_id}.json + knowledge/knowledge_index.json
Source: src/agent_system/models.py

| Field | Type | Description |
|---|---|---|
| entry_id | str | Unique ID |
| phase_id | str | Phase that created it |
| task_id | str | Task that created it |
| category | str | Knowledge category |
| title | str | Short description |
| content | str | Full knowledge content |
| tags | list[str] | Retrieval tags |
| source_agent | str | Agent that captured it |
| created_at | str | When captured |
| retrieval_count | int | How many times retrieved |
| last_retrieved | str | Last retrieval timestamp |


### 7. SkillImprovement
File: knowledge/skill_improvements.jsonl (append-only) + knowledge/agent_skills.json
Source: src/agent_system/skill_tracker.py

| Field | Type | Description |
|---|---|---|
| improvement_id | str | Unique ID |
| agent_role | str | Which agent improved |
| phase_id | str | Phase context |
| task_id | str | Task context |
| run_id | str | Run context |
| skill_name | str | Skill identifier |
| category | str | review_remediation / failure_learning / knowledge_reuse / knowledge_capture |
| before | str | State before improvement |
| after | str | State after improvement |
| reason | str | What triggered it |
| evidence | str | Supporting evidence |
| impact | str | Expected impact |
| timestamp | str | When recorded |


## New Entities (Phase 0A)

### 8. HumanIntervention
File: evidence/human_interventions.jsonl (append-only)
Source: src/agent_system/models.py

| Field | Type | Description |
|---|---|---|
| intervention_id | str | Unique ID |
| run_id | str | Links to run |
| phase_id | str | Links to phase |
| task_id | str | Links to task |
| category | HumanInterventionCategory | APPROVAL / CORRECTION / CLARIFICATION / OVERRIDE / ESCALATION / CONFIGURATION / REJECTION |
| agent_role | str | Agent that triggered intervention |
| reason | str | Why intervention was needed |
| decision | str | What the human decided |
| impact | str | Impact on task/phase |
| timestamp | str | When it occurred |


### 9. AgentDecision
File: evidence/agent_decisions.jsonl (append-only)
Source: src/agent_system/models.py

| Field | Type | Description |
|---|---|---|
| decision_id | str | Unique ID |
| run_id | str | Links to run |
| phase_id | str | Links to phase |
| task_id | str | Links to task |
| agent_role | str | Agent that made the decision |
| decision_type | str | E.g., TASK_EVALUATION, REVIEW_VERDICT, RESEARCH_NEEDED |
| decision | str | The decision made |
| alternatives | list[str] | Other options considered |
| rationale | str | Why this decision |
| confidence | str | Agent's confidence level |
| timestamp | str | When decided |


### 10. TestExecution
File: evidence/test_executions.jsonl (append-only)
Source: src/agent_system/models.py

| Field | Type | Description |
|---|---|---|
| execution_id | str | Unique ID |
| run_id | str | Links to run |
| phase_id | str | Links to phase |
| task_id | str | Links to task |
| test_name | str | Test suite or test name |
| passed | int | Tests passed |
| failed | int | Tests failed |
| skipped | int | Tests skipped |
| errors | int | Tests errored |
| total | int | Computed: passed + failed + skipped + errors |
| duration_seconds | float | Test execution time |
| coverage_pct | float | Code coverage (-1 if not available) |
| metric_type | MetricType | MEASURED or UNAVAILABLE |
| timestamp | str | When executed |


### 11. PhaseMetrics
File: evidence/phase_metrics.json (atomic write, keyed by phase_id)
Source: src/agent_system/models.py

| Field | Type | Description |
|---|---|---|
| phase_id | str | Phase identifier |
| run_id | str | Links to run |
| task_count | int | Total tasks in phase |
| tasks_completed | int | Successfully completed |
| tasks_failed | int | Failed tasks |
| total_duration_seconds | float | Phase wall-clock time |
| remediation_cycles | int | Total remediation loops |
| findings_count | int | Total review findings |
| findings_blocker | int | BLOCKER severity |
| findings_high | int | HIGH severity |
| knowledge_entries_created | int | Knowledge captured |
| knowledge_reuse_count | int | Knowledge reused |
| human_intervention_count | int | Human interventions |
| agent_decision_count | int | Recorded decisions |
| test_pass_count | int | Tests passed |
| test_fail_count | int | Tests failed |
| metric_type | MetricType | Always DERIVED |
| computed_at | str | When computed |


### 12. KnowledgeReuseEvent
File: evidence/knowledge_reuse.jsonl (append-only)
Source: src/agent_system/models.py

| Field | Type | Description |
|---|---|---|
| event_id | str | Unique ID |
| run_id | str | Links to run |
| phase_id | str | Current phase |
| task_id | str | Current task |
| agent_role | str | Agent using the knowledge |
| knowledge_entry_id | str | Links to KnowledgeEntry |
| knowledge_title | str | Title for readability |
| source_phase | str | Phase that created the knowledge |
| application | str | How it was applied |
| outcome | str | Result of application |
| timestamp | str | When reused |


## Entity Relationships

    Run (1) ---> (*) Phase ---> (*) Task ---> (*) TelemetryEvent
                                    |
                                    +---> (*) ReviewFinding
                                    +---> (*) AgentHandoff
                                    +---> (*) AgentDecision
                                    +---> (*) TestExecution
                                    +---> (*) HumanIntervention
                                    +---> (*) KnowledgeReuseEvent
                                    +---> (*) KnowledgeEntry
                                    +---> (*) SkillImprovement
                               Phase ---> (1) PhaseMetrics


## Storage Strategy

- Append-only JSONL for high-frequency event records (telemetry, decisions, interventions, tests, reuse)
- Atomic-write JSON for structured state (tasks, phases, findings, phase metrics, knowledge index)
- Individual JSON files for knowledge entries (one per entry)
- JSONL for skill improvements (append-only log)
- Markdown files for human-readable summaries (auto-generated)
