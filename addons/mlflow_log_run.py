#!/usr/bin/env python3
"""
mlflow_log_run.py
Log a Tower run directory into MLflow (local file store by default).

- Reads run_context.json + run_summary.json if present.
- Logs params/tags/metrics and uploads artifacts (json + logs).
- Does NOT require a server.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def _read_json(p: Path) -> Optional[Dict[str, Any]]:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", required=True, help="Path to a Tower run dir containing run_context.json")
    ap.add_argument("--tracking_uri", default="", help="Optional MLflow tracking URI. Default: file:tower/addons/mlruns")
    ap.add_argument("--experiment", default="tower", help="MLflow experiment name (default: tower)")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        print(f"ERROR: run_dir not found or not a directory: {run_dir}")
        return 2

    try:
        import mlflow  # type: ignore
    except Exception as e:
        print("ERROR: mlflow not installed in this environment.")
        print("Fix: activate tower/.venv_addons and install requirements_addons.txt")
        print(f"Details: {e}")
        return 3

    repo_root = Path.cwd().resolve()
    default_store = (repo_root / "tower" / "addons" / "mlruns").resolve()
    tracking_uri = args.tracking_uri.strip() or f"file:{default_store.as_posix()}"

    ctx = _read_json(run_dir / "run_context.json") or {}
    summary = _read_json(run_dir / "run_summary.json") or {}

    card_id = str(ctx.get("card_id", "UNKNOWN"))
    run_id = str(ctx.get("run_id", run_dir.name))
    model = str(ctx.get("model", "UNKNOWN"))
    session = str(ctx.get("session_id", ctx.get("session", "UNKNOWN")))
    machine = str(ctx.get("machine", "UNKNOWN"))
    git_sha = str(ctx.get("git_sha", ctx.get("git", {}).get("sha", "UNKNOWN")))
    spec_version = str(ctx.get("spec_version", "UNKNOWN"))

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(args.experiment)

    with mlflow.start_run(run_name=run_id):
        # params/tags (small + stable)
        mlflow.set_tag("tower.card_id", card_id)
        mlflow.set_tag("tower.run_id", run_id)
        mlflow.set_tag("tower.model", model)
        mlflow.set_tag("tower.session", session)
        mlflow.set_tag("tower.machine", machine)
        mlflow.set_tag("tower.git_sha", git_sha)
        mlflow.set_tag("tower.spec_version", spec_version)

        # metrics (best-effort)
        def _metric(name: str, val: Any) -> None:
            try:
                if val is None:
                    return
                mlflow.log_metric(name, float(val))
            except Exception:
                return

        _metric("exit_code", summary.get("exit_code"))
        _metric("duration_seconds", summary.get("duration_seconds"))
        _metric("wall_seconds", summary.get("wall_seconds"))

        # Log json as artifacts
        for fn in ["run_context.json", "run_summary.json"]:
            p = run_dir / fn
            if p.exists():
                mlflow.log_artifact(p.as_posix(), artifact_path="tower_run")

        # Log logs/ directory if present
        logs_dir = run_dir / "logs"
        if logs_dir.exists() and logs_dir.is_dir():
            for p in logs_dir.rglob("*"):
                if p.is_file():
                    # preserve relative structure
                    rel = p.relative_to(run_dir)
                    mlflow.log_artifact(p.as_posix(), artifact_path=f"tower_run/{rel.parent.as_posix()}")

        # Log anything else small-ish (best-effort): *.md, *.txt, *.csv, *.json in run_dir
        for p in run_dir.glob("*"):
            if not p.is_file():
                continue
            if p.name in ("run_context.json", "run_summary.json"):
                continue
            if p.suffix.lower() in (".md", ".txt", ".csv", ".json"):
                mlflow.log_artifact(p.as_posix(), artifact_path="tower_run/misc")

    print("OK")
    print(f"tracking_uri: {tracking_uri}")
    print(f"experiment: {args.experiment}")
    print(f"logged run_dir: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
