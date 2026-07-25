# How to Run

## Prerequisites

- Python 3.11+
- macOS (tested on Apple Silicon M3)

## Setup

1. Create and activate virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate

2. Install dependencies:

    pip install -e ".[dev]"

## Commands

### Dry Run (Synthetic Validation)

    python -m agent_system.cli dry-run -v

Runs a synthetic phase through the full pipeline: planning, delegation, implementation, review, remediation, knowledge capture. Validates all system components without requiring API keys.

### Run a Specific Phase

    python -m agent_system.cli run --phase 0A -v

### Run from Next Eligible Phase

    python -m agent_system.cli run -v

### Check System Status

    python -m agent_system.cli status

### Resume After Restart

    python -m agent_system.cli resume -v

### Validate Components

    python -m agent_system.cli validate -v

## Running Tests

    python -m pytest tests/ -v

## Environment Variables

- ANTHROPIC_API_KEY: Required for live (non-dry-run) execution with Claude API

## Output Locations

- state/: Persistent state (JSON)
- telemetry/: Event logs (JSONL per run)
- logs/: Application logs
- artifacts/: Dry-run results and generated artifacts
- knowledge/: Captured lessons and SKILLS_INDEX.md
