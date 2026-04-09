#!/usr/bin/env python3
"""
MLflow Run Wrapper for Tower

Wraps command execution with MLflow experiment tracking.
If MLflow is not installed, prints instructions and exits non-zero.
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
from typing import Optional

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
RUNS_DIR = SCRIPT_DIR / "runs"
MLRUNS_DIR = SCRIPT_DIR / "mlruns"


def _mlflow_available() -> bool:
    """Check if MLflow is installed."""
    try:
        import mlflow
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


def run_with_mlflow(
    name: str,
    cmd: str,
    card_id: Optional[str] = None,
    model: Optional[str] = None,
    session: Optional[str] = None,
    tags: Optional[list] = None
) -> int:
    """
    Run command with MLflow tracking.

    Args:
        name: Run name/label
        cmd: Command to execute
        card_id: Optional card ID
        model: Optional model name
        session: Optional session name
        tags: Optional list of tags

    Returns:
        Command exit code
    """
    run_id = _generate_run_id()
    runs_dir = _ensure_runs_dir()
    run_dir = runs_dir / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    stdout_file = run_dir / "stdout.log"
    stderr_file = run_dir / "stderr.log"
    summary_file = run_dir / "wrapper_run.json"

    start_time = datetime.now(timezone.utc)
    cwd = os.getcwd()

    # Run the command
    try:
        with open(stdout_file, "w") as fout, open(stderr_file, "w") as ferr:
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=fout,
                stderr=ferr,
                cwd=cwd,
                timeout=3600  # 1 hour max
            )
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        exit_code = -1
    except Exception as e:
        print(f"ERROR: Command failed: {e}", file=sys.stderr)
        exit_code = -1

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    # Write local summary
    summary = {
        "run_id": run_id,
        "name": name,
        "command": cmd,
        "card_id": card_id,
        "model": model,
        "session": session,
        "tags": tags or [],
        "cwd": cwd,
        "exit_code": exit_code,
        "duration_sec": round(duration, 2),
        "started_at": start_time.isoformat(),
        "ended_at": end_time.isoformat(),
        "paths": {
            "stdout": str(stdout_file),
            "stderr": str(stderr_file)
        }
    }

    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    # Log to MLflow if available
    if _mlflow_available():
        try:
            import mlflow

            # Set tracking URI
            tracking_uri = os.environ.get(
                "MLFLOW_TRACKING_URI",
                f"file:{MLRUNS_DIR}"
            )
            mlflow.set_tracking_uri(tracking_uri)

            # Set experiment
            experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "tower")
            mlflow.set_experiment(experiment_name)

            # Start run
            with mlflow.start_run(run_name=name):
                # Log parameters
                mlflow.log_param("command", cmd[:250])  # Truncate if too long
                mlflow.log_param("cwd", cwd[:250])

                if card_id:
                    mlflow.log_param("card_id", card_id)
                if model:
                    mlflow.log_param("model", model)
                if session:
                    mlflow.log_param("session", session)

                # Log metrics
                mlflow.log_metric("exit_code", exit_code)
                mlflow.log_metric("duration_sec", duration)

                # Log artifacts
                mlflow.log_artifact(str(stdout_file))
                mlflow.log_artifact(str(stderr_file))
                mlflow.log_artifact(str(summary_file))

                # Set tags
                if tags:
                    for tag in tags:
                        mlflow.set_tag(f"tag_{tag}", "true")

            print(f"[mlflow_wrapper] MLflow run logged to {tracking_uri}")

        except Exception as e:
            print(f"[mlflow_wrapper] MLflow logging failed: {e}", file=sys.stderr)
    else:
        print("[mlflow_wrapper] MLflow not installed, skipped remote logging")

    # Print summary
    print(f"[mlflow_wrapper] Run ID: {run_id}")
    print(f"[mlflow_wrapper] Exit code: {exit_code}")
    print(f"[mlflow_wrapper] Duration: {duration:.2f}s")
    print(f"[mlflow_wrapper] Outputs: {run_dir}")

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="MLflow Run Wrapper for Tower")
    parser.add_argument("--name", required=True, help="Run name/label")
    parser.add_argument("--cmd", required=True, help="Command to execute")
    parser.add_argument("--card", help="Card ID")
    parser.add_argument("--model", help="Model name")
    parser.add_argument("--session", help="Session name")
    parser.add_argument("--tags", help="Comma-separated tags")

    args = parser.parse_args()

    if not _mlflow_available():
        print("WARNING: MLflow not installed. Install with: pip install mlflow")
        print("         Continuing with local logging only.")

    tags = args.tags.split(",") if args.tags else None

    return run_with_mlflow(
        name=args.name,
        cmd=args.cmd,
        card_id=args.card,
        model=args.model,
        session=args.session,
        tags=tags
    )


if __name__ == "__main__":
    sys.exit(main())
