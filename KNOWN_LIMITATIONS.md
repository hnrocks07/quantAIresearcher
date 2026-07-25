# Known Limitations

## Current State: Bootstrap Validated (Dry-Run Mode)

The agent system has passed synthetic dry-run validation and all 79 tests. The following limitations apply at this stage.

## Telemetry Unavailable in Current Mode

| Metric | Status | Reason |
|---|---|---|
| token_usage | UNAVAILABLE | No Claude API integration in dry-run; available when ANTHROPIC_API_KEY is set and live execution is used |
| cost | UNAVAILABLE | Cannot derive cost without token usage data |
| model_identifier_from_api | UNAVAILABLE | API response headers not available in dry-run mode |
| actual_model_version | UNAVAILABLE | Claude API may expose model version in response metadata; captured when available |

These metrics will transition to MEASURED once live API integration is active.

## Agent Execution

- Agents currently return simulated (dry-run) responses. Live execution requires ANTHROPIC_API_KEY.
- The system does not yet implement streaming or multi-turn agent conversations within a single task.
- Agent context window management (for very large tasks) is not yet implemented.
- Inter-agent communication is structured through the orchestrator, not direct.

## Concurrency

- Max 2 concurrent LLM agents is enforced but the current implementation uses sequential execution within each task pipeline. True parallel execution across independent tasks within a phase is not yet implemented.
- The semaphore-based resource manager handles contention but does not implement priority queuing.

## State and Persistence

- State files use JSON with atomic writes. Under extreme conditions (disk full, filesystem corruption), recovery may require manual intervention.
- There is no automatic state migration mechanism if the schema changes between versions.
- Checkpoint granularity is per-phase. A crash mid-task within a phase will replay that task from the beginning.

## Knowledge Store and Skill Evolution

- Knowledge retrieval uses simple tag matching. Semantic similarity search is not implemented.
- No automatic knowledge pruning or relevance decay.
- Knowledge entries are not deduplicated automatically.
- Skill improvements are tracked per-agent with history, but "improvement level" is descriptive text, not a quantitative metric.
- The SKILL_EVOLUTION.md document is auto-generated; it grows linearly with the number of improvements. No summarization or pruning yet.

## Evidence Framework

- Evidence collection is structural and relies on the orchestrator recording events at each handoff point. If the orchestrator itself crashes between an agent completing and the telemetry write, that event could be lost.
- Duration metrics in dry-run mode are near-zero (simulated responses are instant).

## Hardware Constraints

- Designed for MacBook Air M3, 8 cores, 16GB. The system does not dynamically detect or adapt to available resources beyond the configured limits.
- No disk space monitoring or automatic cleanup.

## Not Implemented Yet (Future Phases)

- Claude API integration (Phase 0A will configure this)
- PostgreSQL database (Phase 1)
- Market data ingestion (Phase 3)
- Strategy execution sandbox (Phase 5+)
- UI/Dashboard (Phase 9)
