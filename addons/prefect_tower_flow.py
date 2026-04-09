#!/usr/bin/env python3
"""
prefect_tower_flow.py
Optional Prefect wrapper that shells out to existing Tower scripts.
Does not modify Tower scripts or app code.

Tasks supported:
- validate: bash tower/scripts/validate_all.sh
- dashboard: bash tower/scripts/tower_dashboard.sh
- night: bash tower/scripts/night_runner.sh   (if present)
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> int:
    print(f"+ {' '.join(cmd)}")
    p = subprocess.run(cmd)
    return int(p.returncode)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=["validate", "dashboard", "night"], help="Which Tower task to run")
    args = ap.parse_args()

    try:
        from prefect import flow, task  # type: ignore
    except Exception as e:
        print("ERROR: Prefect not installed in this environment.")
        print("Fix: activate tower/.venv_addons and install requirements_addons.txt")
        print(f"Details: {e}")
        return 3

    repo_root = Path.cwd().resolve()
    tower_scripts = repo_root / "tower" / "scripts"

    validate_sh = tower_scripts / "validate_all.sh"
    dashboard_sh = tower_scripts / "tower_dashboard.sh"
    night_sh = tower_scripts / "night_runner.sh"

    @task
    def run_validate() -> int:
        if not validate_sh.exists():
            print(f"MISSING: {validate_sh}")
            return 2
        return _run(["bash", validate_sh.as_posix()])

    @task
    def run_dashboard() -> int:
        if not dashboard_sh.exists():
            print(f"MISSING: {dashboard_sh}")
            return 2
        return _run(["bash", dashboard_sh.as_posix()])

    @task
    def run_night() -> int:
        if not night_sh.exists():
            print(f"MISSING: {night_sh}")
            return 2
        return _run(["bash", night_sh.as_posix()])

    @flow(name="tower_addons_flow")
    def tower_addons_flow(task_name: str) -> int:
        if task_name == "validate":
            return run_validate()
        if task_name == "dashboard":
            return run_dashboard()
        if task_name == "night":
            return run_night()
        return 2

    rc = tower_addons_flow(args.task)
    print(f"done task={args.task} rc={rc}")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
