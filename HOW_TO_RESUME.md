# How to Resume

The agent system persists all state to disk using atomic JSON writes. It can safely resume after:

- Claude session restart
- Process crash
- Application restart
- Machine reboot

## How Persistence Works

1. Every state change writes to JSON files under state/ using atomic write (temp file + rename)
2. The current run ID persists in state/current_run.json
3. Phase and task states persist in state/phases.json and state/tasks.json
4. Checkpoints are saved after each phase completes in state/checkpoint.json
5. Telemetry events persist as JSONL files under telemetry/
6. Knowledge entries persist under knowledge/

## Resuming

After any interruption:

    source .venv/bin/activate
    python -m agent_system.cli resume -v

This will:
1. Detect the existing run ID from state/current_run.json
2. Load the checkpoint from state/checkpoint.json
3. Identify the current phase and any incomplete tasks
4. Continue execution from the last known good state

## Checking Current State

    python -m agent_system.cli status

Shows: current phase, active tasks, completed phases, resource status, knowledge entries, and whether resumable state exists.

## Manual Recovery

If automated resume fails:

1. Check state/current_phase.json for the current phase
2. Check state/tasks.json for task statuses
3. Run the specific phase manually:

    python -m agent_system.cli run --phase PHASE_ID -v

## Clearing State for a Fresh Start

Remove or archive the state/ directory contents (except project_config.json and dependencies.json) to start fresh. Knowledge under knowledge/ is preserved across runs.
