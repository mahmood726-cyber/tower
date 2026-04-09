#!/usr/bin/env python3
"""
Tower MLflow Run Logger

Logs a Tower run into MLflow WITHOUT changing Tower artifact layout.
If mlflow is not installed, writes an addon_event with status NOT_INSTALLED and exits 0.

Usage:
    python3 tower/scripts/addons/mlflow_log_run.py \\
        --card CARD-XXX \\
        --run_dir <path to tower/artifacts/.../run_<run_id>/> \\
        --spec_version v1.5.5
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

SPEC_VERSION = "v1.5.7"


def get_tower_root():
    """Get Tower root directory."""
    script_dir = Path(__file__).parent
    return script_dir.parent.parent


def atomic_write_json(path: Path, data: dict):
    """Write JSON atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix('.tmp')

    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())

    if os.name == 'nt' and path.exists():
        path.unlink()
    os.rename(tmp_path, path)


def load_json_safe(path: Path) -> dict:
    """Load JSON file safely, return empty dict on failure."""
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def write_addon_event(run_dir: Path, card_id: str, run_id: str,
                      status: str, details: dict = None,
                      error_message: str = None):
    """Write addon event to run directory."""
    event = {
        "spec_version": SPEC_VERSION,
        "event_type": "MLFLOW_LOG",
        "timestamp": datetime.now().isoformat(),
        "card_id": card_id,
        "run_id": run_id,
        "addon": "mlflow",
        "status": status,
        "schema_validation": "SKIPPED",
        "details": details or {},
        "pointers": []
    }

    if error_message:
        event["error_message"] = error_message

    event_path = run_dir / "addon_mlflow_event.json"
    atomic_write_json(event_path, event)
    return event_path


def main():
    parser = argparse.ArgumentParser(description='Tower MLflow Run Logger')
    parser.add_argument('--card', required=True, help='Card ID')
    parser.add_argument('--run_dir', required=True, help='Path to run directory')
    parser.add_argument('--spec_version', default=SPEC_VERSION, help='Spec version')

    args = parser.parse_args()

    card_id = args.card
    run_dir = Path(args.run_dir)
    spec_version = args.spec_version

    # Extract run_id from directory name
    run_id = run_dir.name.replace("run_", "") if run_dir.name.startswith("run_") else None

    tower_root = get_tower_root()
    receipts_dir = tower_root / "addons" / "mlflow" / "state" / "receipts"
    mlruns_dir = tower_root / "addons" / "mlflow" / "state" / "mlruns"

    # Check if mlflow is installed
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
        HAS_MLFLOW = True
    except ImportError:
        HAS_MLFLOW = False

    if not HAS_MLFLOW:
        print("MLflow not installed. Writing NOT_INSTALLED event.")
        write_addon_event(
            run_dir, card_id, run_id,
            status="NOT_INSTALLED",
            details={"message": "pip install mlflow to enable MLflow logging"}
        )

        # Write receipt
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt = {
            "spec_version": spec_version,
            "receipt_type": "mlflow_log",
            "created_at": datetime.now().isoformat(),
            "card_id": card_id,
            "run_id": run_id,
            "status": "NOT_INSTALLED",
            "mlflow_run_id": None
        }
        atomic_write_json(receipts_dir / f"{run_id or 'unknown'}.json", receipt)
        print(f"Receipt written: {receipts_dir / f'{run_id or 'unknown'}.json'}")
        return 0

    # Load run context and summary
    run_context = load_json_safe(run_dir / "run_context.json")
    run_summary = load_json_safe(run_dir / "run_summary.json")

    if not run_context:
        print(f"WARNING: run_context.json not found in {run_dir}")

    # Set up MLflow
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", f"file:{mlruns_dir}")
    experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "Tower")

    mlflow.set_tracking_uri(tracking_uri)

    # Get or create experiment
    try:
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment is None:
            experiment_id = mlflow.create_experiment(experiment_name)
        else:
            experiment_id = experiment.experiment_id
    except Exception as e:
        print(f"ERROR: Could not create/get experiment: {e}")
        write_addon_event(run_dir, card_id, run_id, "FAILED", error_message=str(e))
        return 1

    # Start MLflow run
    try:
        with mlflow.start_run(experiment_id=experiment_id, run_name=f"{card_id}_{run_id}") as mlrun:
            mlflow_run_id = mlrun.info.run_id

            # Log tags
            mlflow.set_tag("card_id", card_id)
            if run_id:
                mlflow.set_tag("run_id", run_id)
            if run_context.get("model"):
                mlflow.set_tag("model", run_context["model"])
            if run_context.get("machine"):
                mlflow.set_tag("machine", run_context["machine"])
            if run_context.get("session"):
                mlflow.set_tag("session", run_context["session"])
            if run_context.get("git_sha"):
                mlflow.set_tag("git_sha", run_context["git_sha"])
            mlflow.set_tag("spec_version", spec_version)

            # Log metrics
            if run_summary.get("duration_seconds") is not None:
                mlflow.log_metric("duration_seconds", run_summary["duration_seconds"])
            if run_summary.get("exit_code") is not None:
                mlflow.log_metric("exit_code", run_summary["exit_code"])

            # Log artifacts
            for artifact_name in ["run_context.json", "run_summary.json", "stdout.log", "stderr.log"]:
                artifact_path = run_dir / artifact_name
                if artifact_path.exists():
                    mlflow.log_artifact(str(artifact_path))

            # Check for validator report
            for child in run_dir.iterdir():
                if child.name == "validator_report.json":
                    mlflow.log_artifact(str(child))
                    report = load_json_safe(child)
                    if report.get("passed_count") is not None:
                        mlflow.log_metric("validators_passed", report["passed_count"])
                    if report.get("failed_count") is not None:
                        mlflow.log_metric("validators_failed", report["failed_count"])

            print(f"MLflow run logged: {mlflow_run_id}")

    except Exception as e:
        print(f"ERROR: MLflow logging failed: {e}")
        write_addon_event(run_dir, card_id, run_id, "FAILED", error_message=str(e))
        return 1

    # Write addon event
    write_addon_event(
        run_dir, card_id, run_id,
        status="OK",
        details={
            "mlflow_run_id": mlflow_run_id,
            "experiment_name": experiment_name,
            "tracking_uri": tracking_uri
        }
    )

    # Write receipt
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "spec_version": spec_version,
        "receipt_type": "mlflow_log",
        "created_at": datetime.now().isoformat(),
        "card_id": card_id,
        "run_id": run_id,
        "status": "OK",
        "mlflow_run_id": mlflow_run_id,
        "experiment_name": experiment_name,
        "tracking_uri": tracking_uri
    }
    receipt_path = receipts_dir / f"{run_id or 'unknown'}.json"
    atomic_write_json(receipt_path, receipt)
    print(f"Receipt written: {receipt_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
