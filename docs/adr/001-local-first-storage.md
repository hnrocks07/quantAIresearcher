# ADR-001: Local-First Storage

Status: Accepted
Date: 2026-07-25
Deciders: Project scope (PROJECT_CONTEXT.md)

## Context

The Local Trading Simulator needs a storage backend for assets, portfolios,
positions, and trades. The platform targets individual developer machines
(macOS/Linux) and must work offline for core features.

Options considered:
1. SQLite — embedded, zero-config, single-file database
2. PostgreSQL — full-featured RDBMS, requires separate server process
3. File-based (JSON/CSV) — simplest, no query capability

## Decision

Use SQLite as the primary storage backend for Phase 0 and the foreseeable
local-first operation of the platform.

## Rationale

- Zero setup: no server process, no credentials, no network dependency
- Single file: trivially portable, backed up, and version-controlled
- Python stdlib support: sqlite3 module ships with Python 3.11+
- Offline-capable: no network required for any core operation
- Sufficient for single-user workloads (which is all this platform supports)
- ACID-compliant with WAL mode for concurrent read/write

## Consequences

Positive:
- Clone-to-run experience: no database installation step
- Tests run without external dependencies
- Backups are file copies

Negative:
- No built-in vector search (pgvector). When vector similarity is needed
  (Phase 2+), either migrate to PostgreSQL or use a separate vector store.
- No concurrent multi-process writes. Acceptable for single-user platform.
- Limited data types compared to PostgreSQL.

## Migration Path

When the platform needs features beyond SQLite (vector search, full-text
search at scale, concurrent writes), introduce PostgreSQL as an optional
backend behind a storage abstraction layer. SQLite remains the default
for local development and testing.
