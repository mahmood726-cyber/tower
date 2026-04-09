#!/usr/bin/env python3
"""
Prefect Flows for Tower

Wraps existing Tower scripts as Prefect flows.
Does NOT require Prefect to be installed for import - only for execution.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
TOWER_ROOT = SCRIPT_DIR.parent.parent
TOWER_SCRIPTS = TOWER_ROOT / "scripts"
RUNS_DIR = SCRIPT_DIR / "runs"


def _prefect_available() -> bool:
    """Check if Prefect is installed."""
    try:
        import prefect
        return True
    except ImportError:
        return False


def _ensure_runs_dir() -> Path:
    """Ensure runs directory exists with today's date."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    runs_dir = RUNS_DIR / today
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir


def _generate_run_id() -> str:
    """Generate unique run ID."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{ts}_{suffix}"


def _run_script(script_name: str, flow_name: str) -> Dict[str, Any]:
    """
    Run a Tower script and capture output.

    Returns summary dict with exit_code, duration_sec, paths.
    """
    script_path = TOWER_SCRIPTS / script_name

    if not script_path.exists():
        return {
            "status": "ERROR",
            "error": f"Script not found: {script_path}",
            "exit_code": 127,
            "duration_sec": 0,
            "paths": []
        }

    run_id = _generate_run_id()
    runs_dir = _ensure_runs_dir()

    out_file = runs_dir / f"{flow_name}_{run_id}.out"
    err_file = runs_dir / f"{flow_name}_{run_id}.err"
    json_file = runs_dir / f"{flow_name}_{run_id}.json"

    start_time = datetime.now(timezone.utc)

    try:
        # Run the script
        with open(out_file, "w") as fout, open(err_file, "w") as ferr:
            result = subprocess.run(
                ["bash", str(script_path)],
                stdout=fout,
                stderr=ferr,
                cwd=str(TOWER_ROOT.parent),  # Repo root
                timeout=3600  # 1 hour max
            )

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        summary = {
            "run_id": run_id,
            "flow_name": flow_name,
            "script": script_name,
            "status": "SUCCESS" if result.returncode == 0 else "FAILED",
            "exit_code": result.returncode,
            "duration_sec": round(duration, 2),
            "started_at": start_time.isoformat(),
            "ended_at": end_time.isoformat(),
            "paths": {
                "stdout": str(out_file.relative_to(TOWER_ROOT.parent)),
                "stderr": str(err_file.relative_to(TOWER_ROOT.parent)),
                "summary": str(json_file.relative_to(TOWER_ROOT.parent))
            }
        }

    except subprocess.TimeoutExpired:
        summary = {
            "run_id": run_id,
            "flow_name": flow_name,
            "script": script_name,
            "status": "TIMEOUT",
            "exit_code": -1,
            "duration_sec": 3600,
            "error": "Script timed out after 1 hour",
            "paths": {}
        }

    except Exception as e:
        summary = {
            "run_id": run_id,
            "flow_name": flow_name,
            "script": script_name,
            "status": "ERROR",
            "exit_code": -1,
            "duration_sec": 0,
            "error": str(e),
            "paths": {}
        }

    # Write summary JSON
    with open(json_file, "w") as f:
        json.dump(summary, f, indent=2)

    return summary


# Flow implementations - only use Prefect decorators if available
def _create_flows():
    """Create Prefect flows if Prefect is available."""
    if not _prefect_available():
        return None, None, None

    from prefect import flow, task

    @task(name="run_tower_script")
    def run_script_task(script_name: str, flow_name: str) -> Dict[str, Any]:
        return _run_script(script_name, flow_name)

    @flow(name="tower_night_runner")
    def tower_night_runner_flow() -> Dict[str, Any]:
        """Run Tower night runner."""
        return run_script_task("night_runner.sh", "tower_night_runner")

    @flow(name="tower_watchdog")
    def tower_watchdog_flow() -> Dict[str, Any]:
        """Run Tower watchdog."""
        return run_script_task("tower_watchdog.sh", "tower_watchdog")

    @flow(name="tower_pc_router")
    def tower_pc_router_flow() -> Dict[str, Any]:
        """Run Tower PC job router."""
        return run_script_task("pc_job_router.sh", "tower_pc_router")

    return tower_night_runner_flow, tower_watchdog_flow, tower_pc_router_flow


def run_flow(flow_name: str) -> int:
    """Run a flow by name."""
    if not _prefect_available():
        print("ERROR: Prefect not installed. Install with: pip install prefect")
        print("       Or activate tower/.venv_addons if available.")
        return 1

    flows = _create_flows()
    if flows[0] is None:
        print("ERROR: Could not create Prefect flows")
        return 1

    night_flow, watchdog_flow, router_flow = flows

    flow_map = {
        "night": night_flow,
        "night_runner": night_flow,
        "tower_night_runner": night_flow,
        "watchdog": watchdog_flow,
        "tower_watchdog": watchdog_flow,
        "router": router_flow,
        "pc_router": router_flow,
        "tower_pc_router": router_flow
    }

    if flow_name not in flow_map:
        print(f"ERROR: Unknown flow: {flow_name}")
        print(f"Available: {list(set(flow_map.values()))}")
        return 1

    print(f"[prefect_flows] Running flow: {flow_name}")
    result = flow_map[flow_name]()

    print(f"[prefect_flows] Result: {result.get('status', 'UNKNOWN')}")
    print(f"[prefect_flows] Exit code: {result.get('exit_code', -1)}")

    if result.get("paths"):
        print(f"[prefect_flows] Outputs: {result['paths']}")

    return 0 if result.get("exit_code", -1) == 0 else 1


def run_without_prefect(flow_name: str) -> int:
    """Run script directly without Prefect (fallback mode)."""
    flow_scripts = {
        "night": "night_runner.sh",
        "night_runner": "night_runner.sh",
        "tower_night_runner": "night_runner.sh",
        "watchdog": "tower_watchdog.sh",
        "tower_watchdog": "tower_watchdog.sh",
        "router": "pc_job_router.sh",
        "pc_router": "pc_job_router.sh",
        "tower_pc_router": "pc_job_router.sh"
    }

    if flow_name not in flow_scripts:
        print(f"ERROR: Unknown flow: {flow_name}")
        return 1

    script = flow_scripts[flow_name]
    print(f"[prefect_flows] Running {script} directly (Prefect not available)")

    result = _run_script(script, flow_name)

    print(f"[prefect_flows] Result: {result.get('status', 'UNKNOWN')}")
    print(f"[prefect_flows] Exit code: {result.get('exit_code', -1)}")

    return 0 if result.get("exit_code", -1) == 0 else 1


def list_flows():
    """List available flows."""
    flows = [
        ("night", "tower_night_runner", "night_runner.sh", "Nightly batch processing"),
        ("watchdog", "tower_watchdog", "tower_watchdog.sh", "Health monitoring"),
        ("router", "tower_pc_router", "pc_job_router.sh", "PC job routing")
    ]

    print("Available flows:")
    print()
    for short, full, script, desc in flows:
        print(f"  {short:12} {full:24} {script:24} {desc}")

    print()
    print(f"Prefect available: {_prefect_available()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Tower Prefect Flows")
    parser.add_argument("--run", help="Run a flow by name")
    parser.add_argument("--list", action="store_true", help="List available flows")
    parser.add_argument("--direct", action="store_true",
                        help="Run directly without Prefect (for testing)")

    args = parser.parse_args()

    if args.list:
        list_flows()
        return 0

    if args.run:
        if args.direct or not _prefect_available():
            return run_without_prefect(args.run)
        return run_flow(args.run)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
