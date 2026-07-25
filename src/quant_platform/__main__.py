"""Entry point — python -m quant_platform [serve|killswitch|trigger|reset]"""

import argparse
import sys

import httpx
import uvicorn

from .config import get_settings


def _serve(args: argparse.Namespace) -> None:
    """Run the main API server (default behaviour)."""
    settings = get_settings()
    uvicorn.run(
        "quant_platform.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.run_mode.value == "local",
        log_level=settings.log_level.lower(),
    )


def _killswitch(args: argparse.Namespace) -> None:
    """Run the kill switch as a standalone process on kill_switch_port."""
    from fastapi import FastAPI
    from .kill_switch import kill_switch

    settings = get_settings()
    ks_app = FastAPI(title="Kill Switch Standalone", version="0.4.0")

    @ks_app.get("/health")
    async def health():
        return {"status": "ok", "service": "kill_switch_standalone"}

    @ks_app.post("/kill-switch/trigger")
    async def trigger(reason: str = "manual"):
        await kill_switch.trigger("standalone_api", reason)
        return {"status": "triggered", "reason": reason}

    @ks_app.post("/kill-switch/reset")
    async def reset():
        await kill_switch.reset("standalone_api")
        return {"status": "reset"}

    @ks_app.get("/kill-switch/status")
    async def status():
        return kill_switch.status()

    @ks_app.post("/kill-switch/heartbeat")
    async def heartbeat():
        kill_switch.heartbeat()
        return {"status": "ok"}

    uvicorn.run(
        ks_app,
        host=settings.api_host,
        port=settings.kill_switch_port,
        log_level=settings.log_level.lower(),
    )


def _trigger(args: argparse.Namespace) -> None:
    """CLI: send a kill switch trigger to the running API."""
    settings = get_settings()
    url = f"http://{settings.api_host}:{settings.api_port}/kill-switch/trigger"
    if settings.api_host == "0.0.0.0":
        url = f"http://127.0.0.1:{settings.api_port}/kill-switch/trigger"
    try:
        resp = httpx.post(url, params={"reason": args.reason}, timeout=10.0)
        print(f"Response ({resp.status_code}): {resp.json()}")
    except httpx.ConnectError:
        print(f"ERROR: Could not connect to API at port {settings.api_port}. Is the server running?")
        sys.exit(1)


def _reset(args: argparse.Namespace) -> None:
    """CLI: send a kill switch reset to the running API."""
    settings = get_settings()
    url = f"http://{settings.api_host}:{settings.api_port}/kill-switch/reset"
    if settings.api_host == "0.0.0.0":
        url = f"http://127.0.0.1:{settings.api_port}/kill-switch/reset"
    try:
        resp = httpx.post(url, timeout=10.0)
        print(f"Response ({resp.status_code}): {resp.json()}")
    except httpx.ConnectError:
        print(f"ERROR: Could not connect to API at port {settings.api_port}. Is the server running?")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="quant_platform",
        description="AI Quant Trading Platform",
    )
    subparsers = parser.add_subparsers(dest="command")

    # serve (default)
    serve_parser = subparsers.add_parser("serve", help="Run the main API server")
    serve_parser.set_defaults(func=_serve)

    # killswitch
    ks_parser = subparsers.add_parser("killswitch", help="Run kill switch as standalone process")
    ks_parser.set_defaults(func=_killswitch)

    # trigger
    trigger_parser = subparsers.add_parser("trigger", help="Trigger kill switch via CLI")
    trigger_parser.add_argument("--reason", default="emergency", help="Reason for triggering")
    trigger_parser.set_defaults(func=_trigger)

    # reset
    reset_parser = subparsers.add_parser("reset", help="Reset kill switch via CLI")
    reset_parser.set_defaults(func=_reset)

    args = parser.parse_args()

    if args.command is None:
        # Default: run serve
        _serve(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
