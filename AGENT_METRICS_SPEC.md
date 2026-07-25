# Agent Metrics Specification

Defines every metric captured by the evidence framework. Each metric is classified as MEASURED, DERIVED, ESTIMATED, or UNAVAILABLE.

- MEASURED: Directly observed from system execution (timestamps, counts, API responses)
- DERIVED: Computed from two or more measured values (rates, ratios)
- ESTIMATED: Inferred when direct measurement is not possible
- UNAVAILABLE: Cannot be captured in the current execution mode (e.g., token usage without API key)


## Agent Team Effectiveness Metrics

| Metric | Type | Formula | Data Source | Collection Point |
|---|---|---|---|---|
| autonomous_completion_rate | DERIVED | (completed tasks without human intervention) / total tasks | StateManager tasks + EvidenceStore interventions | MetricsCalculator.compute_all() |
| human_intervention_rate | DERIVED | tasks with intervention / total tasks | EvidenceStore human_interventions | MetricsCalculator.compute_all() |
| first_pass_review_acceptance | DERIVED | tasks approved on first review (no BLOCKER/HIGH) / total reviewed | TelemetryCollector REVIEW_FINDING events | MetricsCalculator.compute_all() |
| reviewer_defect_discovery_rate | DERIVED | total review findings / tasks reviewed | TelemetryCollector REVIEW_FINDING events | MetricsCalculator.compute_all() |
| autonomous_remediation_rate | DERIVED | remediation cycles / total findings needing remediation | TelemetryCollector REMEDIATION_CYCLE events | MetricsCalculator.compute_all() |
| retry_failure_recovery_rate | DERIVED | recovered retries / total retries | TelemetryCollector all events | MetricsCalculator.compute_all() |


## Execution Metrics

| Metric | Type | Formula | Data Source | Collection Point |
|---|---|---|---|---|
| phase_duration | MEASURED | phase completed_at - started_at | StateManager phases | Orchestrator.execute_phase() |
| task_duration | MEASURED | task completed_at - started_at | StateManager tasks | Orchestrator.execute_task() |
| total_duration_seconds | MEASURED | sum of all event durations | TelemetryCollector events | MetricsCalculator.compute_all() |
| total_tasks | MEASURED | count of all tasks | StateManager tasks | MetricsCalculator.compute_all() |
| completed_tasks | MEASURED | count of COMPLETED tasks | StateManager tasks | MetricsCalculator.compute_all() |
| failed_tasks | MEASURED | count of FAILED tasks | StateManager tasks | MetricsCalculator.compute_all() |


## Model Usage Metrics

| Metric | Type | Condition | Data Source | Collection Point |
|---|---|---|---|---|
| model_token_usage | MEASURED / UNAVAILABLE | MEASURED when ANTHROPIC_API_KEY is set and API returns usage data; UNAVAILABLE in dry-run or CLI mode | TelemetryEvent.token_usage | TelemetryCollector.record_event() |
| model_cost | MEASURED / UNAVAILABLE | MEASURED when token usage is available and pricing is known; UNAVAILABLE otherwise | TelemetryEvent.cost | TelemetryCollector.record_event() |
| model_identifier | MEASURED / UNAVAILABLE | MEASURED from API response headers when available; UNAVAILABLE in dry-run | TelemetryEvent.model_identifier | BaseAgent.run() |


## Quality Metrics

| Metric | Type | Formula | Data Source | Collection Point |
|---|---|---|---|---|
| test_pass_rate | DERIVED | total tests passed / total tests run | EvidenceStore test_executions | MetricsCalculator.compute_all() |
| knowledge_reuse_rate | DERIVED | tasks using prior knowledge / total tasks | EvidenceStore knowledge_reuse | MetricsCalculator.compute_all() |
| findings_count | MEASURED | count of review findings | StateManager review_findings | Orchestrator.execute_task() |
| findings_blocker | MEASURED | count of BLOCKER severity findings | StateManager review_findings | Orchestrator.execute_task() |
| findings_high | MEASURED | count of HIGH severity findings | StateManager review_findings | Orchestrator.execute_task() |
| remediation_cycles | MEASURED | count of remediation loops per task | Task.remediation_cycles | Orchestrator.execute_task() |


## Evidence Integrity Metrics

| Metric | Type | Formula | Data Source | Collection Point |
|---|---|---|---|---|
| human_intervention_count | MEASURED | count of intervention records | EvidenceStore human_interventions | EvidenceStore.record_human_intervention() |
| agent_decision_count | MEASURED | count of decision records | EvidenceStore agent_decisions | EvidenceStore.record_decision() |
| knowledge_entries_created | MEASURED | count of knowledge entries stored | KnowledgeStore | Orchestrator.execute_task() |
| skill_improvement_count | MEASURED | count of skill improvements | SkillTracker | SkillTracker.record_improvement() |


## Per-Phase Aggregate (PhaseMetrics)

Computed at the end of each phase by MetricsCalculator.compute_phase_metrics(). All fields are DERIVED from the phase's constituent tasks and evidence records. Stored in evidence/phase_metrics.json.

Fields: task_count, tasks_completed, tasks_failed, total_duration_seconds, remediation_cycles, findings_count, findings_blocker, findings_high, knowledge_entries_created, knowledge_reuse_count, human_intervention_count, agent_decision_count, test_pass_count, test_fail_count.


## UNAVAILABLE Semantics

When a metric is UNAVAILABLE, the system:
1. Records it with metric_type = UNAVAILABLE
2. Stores the reason why it is unavailable
3. Never fabricates a value or estimates without marking it ESTIMATED
4. Transitions to MEASURED automatically when the data source becomes available (e.g., API key is configured)

The get_unavailable_metrics() method on TelemetryCollector lists all currently unavailable metrics with reasons.
