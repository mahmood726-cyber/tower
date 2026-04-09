#!/usr/bin/env python3
"""
Tower Prefect Flows

Prefect flows for Tower operations:
- validate: Run validation checks
- daily: Run daily maintenance (gatecheck + dashboard)
- night: Run night batch queue

Usage:
    python3 tower/addons/prefect/flows/tower_flow.py validate
    python3 tower/addons/prefect/flows/tower_flow.py daily
    python3 tower/addons/prefect/flows/tower_flow.py night

If prefect is not installed, prints installation guidance.
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

SPEC_VERSION = "v1.5.5"


def get_tower_root():
    """Get Tower root directory."""
    script_dir = Path(__file__).parent
    return script_dir.parent.parent.parent


# Check if Prefect is installed
try:
    from prefect import flow, task, get_run_logger
    HAS_PREFECT = True
except ImportError:
    HAS_PREFECT = False


def run_shell_command(cmd: str, cwd: str = None, description: str = None) -> dict:
    """Run a shell command and return result dict."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600
        )
        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": cmd,
            "description": description
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "Command timed out after 600 seconds",
            "command": cmd,
            "description": description
        }
    except Exception as e:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "command": cmd,
            "description": description
        }


if HAS_PREFECT:
    @task(name="validate_all")
    def task_validate_all():
        """Run tower validation."""
        logger = get_run_logger()
        tower_root = get_tower_root()
        logger.info(f"Running validation in {tower_root}")

        result = run_shell_command(
            "bash scripts/validate_all.sh",
            cwd=str(tower_root),
            description="Tower validation"
        )

        if result["success"]:
            logger.info("Validation passed")
        else:
            logger.error(f"Validation failed: {result['stderr']}")

        return result

    @task(name="gatecheck")
    def task_gatecheck():
        """Run tower gatecheck."""
        logger = get_run_logger()
        tower_root = get_tower_root()
        logger.info("Running gatecheck")

        result = run_shell_command(
            "bash scripts/tower_gatecheck.sh",
            cwd=str(tower_root),
            description="Tower gatecheck"
        )

        if result["success"]:
            logger.info("Gatecheck completed")
        else:
            logger.warning(f"Gatecheck issues: {result['stderr']}")

        return result

    @task(name="dashboard")
    def task_dashboard():
        """Generate tower dashboard."""
        logger = get_run_logger()
        tower_root = get_tower_root()
        logger.info("Generating dashboard")

        # Use Python dashboard script for Windows compatibility
        result = run_shell_command(
            "python scripts/tower_dashboard.py",
            cwd=str(tower_root),
            description="Tower dashboard"
        )

        if result["success"]:
            logger.info("Dashboard generated")
        else:
            logger.error(f"Dashboard failed: {result['stderr']}")

        return result

    @task(name="night_runner")
    def task_night_runner():
        """Run night batch queue."""
        logger = get_run_logger()
        tower_root = get_tower_root()
        logger.info("Running night batch queue")

        result = run_shell_command(
            "bash scripts/night_runner.sh",
            cwd=str(tower_root),
            description="Night runner"
        )

        if result["success"]:
            logger.info("Night runner completed")
        else:
            logger.warning(f"Night runner issues: {result['stderr']}")

        return result

    @flow(name="tower-validate")
    def flow_validate():
        """Validation flow - runs validate_all.sh"""
        logger = get_run_logger()
        logger.info("Starting Tower validation flow")

        result = task_validate_all()
        return {"validate": result}

    @flow(name="tower-daily")
    def flow_daily():
        """Daily maintenance flow - validate, gatecheck, dashboard"""
        logger = get_run_logger()
        logger.info("Starting Tower daily maintenance flow")

        results = {}
        results["validate"] = task_validate_all()
        results["gatecheck"] = task_gatecheck()
        results["dashboard"] = task_dashboard()

        success = all(r["success"] for r in results.values())
        logger.info(f"Daily flow completed. Overall success: {success}")

        return results

    @flow(name="tower-night")
    def flow_night():
        """Night batch flow - validate, night_runner, gatecheck, dashboard"""
        logger = get_run_logger()
        logger.info("Starting Tower night batch flow")

        results = {}
        results["validate"] = task_validate_all()
        results["night_runner"] = task_night_runner()
        results["gatecheck"] = task_gatecheck()
        results["dashboard"] = task_dashboard()

        success = all(r["success"] for r in results.values())
        logger.info(f"Night flow completed. Overall success: {success}")

        return results


def write_receipt(flow_name: str, results: dict, tower_root: Path):
    """Write flow execution receipt."""
    receipts_dir = tower_root / "addons" / "prefect" / "state" / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    receipt_file = receipts_dir / f"{flow_name}_{timestamp}.json"

    import json
    receipt = {
        "spec_version": SPEC_VERSION,
        "flow_name": flow_name,
        "executed_at": datetime.now().isoformat(),
        "results": {
            k: {"success": v["success"], "exit_code": v["exit_code"]}
            for k, v in results.items()
        },
        "overall_success": all(r["success"] for r in results.values())
    }

    tmp_file = receipt_file.with_suffix('.tmp')
    with open(tmp_file, 'w') as f:
        json.dump(receipt, f, indent=2)
    os.rename(tmp_file, receipt_file)

    print(f"Receipt written: {receipt_file}")
    return receipt_file


def main():
    if not HAS_PREFECT:
        print("=" * 60)
        print("Prefect is not installed.")
        print("")
        print("To enable Prefect orchestration, install it:")
        print("  pip install prefect")
        print("")
        print("Prefect runs locally by default (no cloud account needed).")
        print("=" * 60)
        return 1

    if len(sys.argv) < 2:
        print("Usage: tower_flow.py <validate|daily|night>")
        return 1

    flow_name = sys.argv[1].lower()
    tower_root = get_tower_root()

    print(f"Running flow: {flow_name}")
    print(f"Tower root: {tower_root}")

    if flow_name == "validate":
        results = flow_validate()
    elif flow_name == "daily":
        results = flow_daily()
    elif flow_name == "night":
        results = flow_night()
    else:
        print(f"Unknown flow: {flow_name}")
        print("Available flows: validate, daily, night")
        return 1

    # Write receipt
    write_receipt(flow_name, results, tower_root)

    # Return exit code based on success
    overall_success = all(r["success"] for r in results.values())
    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
