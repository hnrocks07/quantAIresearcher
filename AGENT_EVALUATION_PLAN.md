# Agent Evaluation Plan

How to evaluate whether the specialized Claude-powered agent team can build a production-grade AI application.


## Evaluation Dimensions

### 1. Autonomous Capability
Can the agents complete tasks without human help?

| Metric | Target | Good | Concerning |
|---|---|---|---|
| autonomous_completion_rate | > 0.70 | > 0.80 | < 0.50 |
| human_intervention_rate | < 0.30 | < 0.20 | > 0.50 |
| correction_decline_rate | decreasing trend | 50%+ reduction by Phase 5 | flat or increasing |

Measurement: MetricsCalculator.compute_all() after each phase.


### 2. Code Quality
Does the agent team produce production-grade code?

| Metric | Target | Good | Concerning |
|---|---|---|---|
| first_pass_review_acceptance | > 0.60 | > 0.75 | < 0.40 |
| reviewer_defect_discovery_rate | stable or decreasing | < 2 findings/task | > 5 findings/task |
| test_pass_rate | > 0.95 | 1.00 | < 0.90 |
| findings_blocker per phase | 0 | 0-1 | > 3 |

Measurement: Review findings from ReviewerAgent, test execution records.


### 3. Learning and Improvement
Do agents get better over time?

| Metric | Target | Good | Concerning |
|---|---|---|---|
| knowledge_reuse_rate | increasing trend | > 0.30 by Phase 3 | 0.00 after Phase 2 |
| skill_improvement_count | increasing | > 5 per phase | 0 after Phase 1 |
| correction_decline_rate | decreasing | 50%+ reduction | no change |
| same-category finding recurrence | decreasing | < 20% recurrence | > 50% recurrence |

Measurement: KnowledgeStore retrieval counts, SkillTracker improvements, ReviewFinding category trends.


### 4. Resilience and Recovery
Can agents handle failures gracefully?

| Metric | Target | Good | Concerning |
|---|---|---|---|
| retry_failure_recovery_rate | > 0.50 | > 0.75 | < 0.25 |
| autonomous_remediation_rate | > 0.60 | > 0.80 | < 0.30 |
| escalation_rate | < 0.20 | < 0.10 | > 0.40 |

Measurement: TelemetryEvent retry/failure events, EvidenceStore remediation records.


### 5. Efficiency
Are agents using resources effectively?

| Metric | Target | Good | Concerning |
|---|---|---|---|
| model_token_usage per task | stable or decreasing | < baseline | 3x+ baseline |
| task_duration trend | stable | < baseline | 3x+ baseline |
| remediation_cycles per task | < 1.0 avg | < 0.5 avg | > 2.0 avg |

Measurement: TelemetryEvent durations, token usage (when available).
Note: Token/cost metrics are UNAVAILABLE in dry-run mode. Baseline established in first live phase.


## Evaluation Cadence

### Per-Task (automatic)
- Record all evidence (decisions, test executions, handoffs, knowledge reuse)
- Record review findings and remediation cycles

### Per-Phase (automatic)
- Compute PhaseMetrics via MetricsCalculator.compute_phase_metrics()
- Save to evidence/phase_metrics.json
- Generate telemetry summary

### Per-Milestone (manual review)
At the following milestones, produce a human-reviewed evaluation report:

1. After Phase 0A (this phase) — Framework validation
2. After Phase 1 — First real code produced; establish baselines
3. After Phase 5 — Mid-project checkpoint; evaluate learning trends
4. After Phase FINAL — Full case study with complete evidence


## Comparison Baselines

Since there is no prior human-only implementation of the same system, baselines are:
- Phase 1 metrics become the initial baseline
- Each subsequent phase is compared to the cumulative average of prior phases
- Improvement trends (slopes) matter more than absolute values
- Industry norms for code review defect rates (2-5 findings per 100 lines) serve as external reference


## What "Good" Looks Like

A successful agent team demonstration shows:
1. Autonomous completion rate above 70% by the midpoint
2. Declining human intervention rate across phases
3. Increasing knowledge reuse — agents apply lessons from earlier phases
4. Review findings decrease in severity over time (fewer BLOCKERs, more INFOs)
5. Test pass rate stays above 95% throughout
6. Remediation cycles decrease — fewer review-fix loops needed
7. No fabricated evidence — all metrics honestly classified


## What the Final Case Study Reports

The FINAL phase produces a case study document structured as:

1. Methodology — How evidence was collected (this plan)
2. Quantitative Results — All metrics with trends across phases
3. Qualitative Analysis — Where agents excelled vs. struggled
4. Learning Evidence — Specific examples of cross-phase knowledge reuse
5. Intervention Analysis — Category distribution, decline trends
6. Limitations — What was UNAVAILABLE, ESTIMATED, or not measurable
7. Conclusion — Evidence-based assessment, not marketing claims

The case study must distinguish MEASURED facts from DERIVED conclusions from ESTIMATED inferences. It must not claim capabilities that the evidence does not support.


## Integrity Rules

1. Never fabricate telemetry data to improve metrics
2. Always mark unavailable metrics as UNAVAILABLE, never as zero
3. Record human interventions even when they make the metrics look worse
4. Do not exclude phases or tasks from evaluation without explicit justification
5. Evidence collection started before product implementation (Phase 0A) — it is not reconstructed after the fact
