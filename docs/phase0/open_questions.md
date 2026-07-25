# Phase 0 — Open Questions

## Resolved

Q1: SQLite vs PostgreSQL for Phase 0?
  Decision: SQLite per PROJECT_CONTEXT.md. PostgreSQL deferred to Phase 1+.

Q2: Pydantic vs dataclasses for domain models?
  Decision: Pydantic v2. Validation + serialization built in.

Q3: Migration tool for SQLite?
  Decision: Plain SQL scripts. Alembic deferred to Phase 1+ with PostgreSQL.

Q4: Where does quant platform code live?
  Decision: src/quant_platform/ — separate from src/agent_system/.

Q5: Python minimum version?
  Decision: 3.11 per PROJECT_CONTEXT.md. pyproject.toml uses >=3.11.

Q6: Frontend for Phase 0?
  Decision: None. CLI-only. FastAPI deferred to Phase 1.

Q7: Test data format?
  Decision: In-memory Python factory functions. No file I/O fixtures.

Q8: Independent review process?
  Decision: Agent system reviewer agent provides independent review.
  For this direct execution, checklist-based self-review with explicit sign-off.

## Deferred (not blocking Phase 0)

Q9: VectorBT MIT vs Pro feature audit — deferred to Phase 1 (backtesting)
Q10: NSE data source selection — deferred to Phase 1 (data ingestion)
Q11: IST trading hours handling — deferred to Phase 1
