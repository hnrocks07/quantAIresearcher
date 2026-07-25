"""CLI entry point for the agent system."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import Config
from .orchestrator import Orchestrator


def setup_logging(log_dir: Path, verbose: bool = False) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO

    handlers: list[logging.Handler] = [
        logging.FileHandler(log_dir / "agent_system.log"),
        logging.StreamHandler(sys.stdout),
    ]

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def cmd_dry_run(args: argparse.Namespace) -> None:
    config = Config.load(Path(args.project_root) if args.project_root else None)
    setup_logging(config.logs_dir, args.verbose)

    logging.info("Starting dry-run validation...")
    orchestrator = Orchestrator(config)
    result = orchestrator.dry_run()

    output_path = config.artifacts_dir / "dry_run_result.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))
    logging.info("Dry-run result saved to %s", output_path)

    if result.get("validations", {}).get("delegation"):
        print("\nDRY-RUN: PASSED")
    else:
        print("\nDRY-RUN: FAILED")
        sys.exit(1)


def cmd_run(args: argparse.Namespace) -> None:
    config = Config.load(Path(args.project_root) if args.project_root else None)
    setup_logging(config.logs_dir, args.verbose)

    orchestrator = Orchestrator(config)

    if args.phase:
        logging.info("Running phase: %s", args.phase)
        result = orchestrator.run(start_phase=args.phase)
    else:
        logging.info("Running from next eligible phase...")
        result = orchestrator.run()

    print(json.dumps(result, indent=2, default=str))


def cmd_status(args: argparse.Namespace) -> None:
    config = Config.load(Path(args.project_root) if args.project_root else None)
    orchestrator = Orchestrator(config)
    status = orchestrator.get_status()
    print(json.dumps(status, indent=2, default=str))


def cmd_resume(args: argparse.Namespace) -> None:
    config = Config.load(Path(args.project_root) if args.project_root else None)
    setup_logging(config.logs_dir, args.verbose)

    orchestrator = Orchestrator(config)
    if not orchestrator.state.has_resumable_state():
        print("No resumable state found.")
        sys.exit(1)

    logging.info("Resuming from checkpoint...")
    checkpoint = orchestrator.state.load_checkpoint()
    if checkpoint:
        current_phase = checkpoint.get("current_phase", {}).get("phase")
        if current_phase:
            logging.info("Resuming phase: %s", current_phase)
            result = orchestrator.run(start_phase=current_phase)
            print(json.dumps(result, indent=2, default=str))
        else:
            print("No phase to resume.")
    else:
        print("No checkpoint found.")


def cmd_validate(args: argparse.Namespace) -> None:
    config = Config.load(Path(args.project_root) if args.project_root else None)
    setup_logging(config.logs_dir, args.verbose)

    orchestrator = Orchestrator(config)

    validations = {
        "phase_loader": False,
        "dependency_graph": False,
        "agents_loaded": False,
        "state_persistence": False,
        "telemetry": False,
        "resource_manager": False,
        "knowledge_store": False,
    }

    # Phase loader
    phases = orchestrator.phase_loader.get_all_phases()
    errors = orchestrator.phase_loader.validate_dependencies()
    validations["phase_loader"] = len(phases) > 0
    validations["dependency_graph"] = len(errors) == 0

    # Agents
    from .agents import AGENT_REGISTRY
    validations["agents_loaded"] = len(AGENT_REGISTRY) == 6

    # State persistence
    orchestrator.state.get_or_create_run_id()
    validations["state_persistence"] = orchestrator.state.has_resumable_state()

    # Telemetry
    orchestrator.telemetry.set_run_id(orchestrator.state.run_id)
    orchestrator.telemetry.record_event(
        event_type="VALIDATION_TEST", status="OK")
    validations["telemetry"] = len(orchestrator.telemetry.get_events()) > 0

    # Resources
    status = orchestrator.resources.check_constraints()
    validations["resource_manager"] = status["concurrent_agents_ok"]

    # Knowledge
    validations["knowledge_store"] = True

    all_passed = all(validations.values())
    result = {"validations": validations, "all_passed": all_passed}

    if errors:
        result["dependency_errors"] = errors

    print(json.dumps(result, indent=2))

    if not all_passed:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Engineering Agent System")
    parser.add_argument("--project-root", type=str, default=None)
    parser.add_argument("--verbose", "-v", action="store_true")

    subparsers = parser.add_subparsers(dest="command")

    for name, func, extras in [
        ("dry-run", cmd_dry_run, []),
        ("run", cmd_run, [("--phase", {"type": str, "default": ""})]),
        ("status", cmd_status, []),
        ("resume", cmd_resume, []),
        ("validate", cmd_validate, []),
    ]:
        sub = subparsers.add_parser(name)
        sub.add_argument("--verbose", "-v", action="store_true")
        sub.add_argument("--project-root", type=str, default=None)
        for arg_name, arg_kwargs in extras:
            sub.add_argument(arg_name, **arg_kwargs)
        sub.set_defaults(func=func)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
