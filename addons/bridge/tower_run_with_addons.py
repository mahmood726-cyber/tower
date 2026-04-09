#!/usr/bin/env python3
"""
Tower Bridge: Run wrapper with LangSmith + MLflow integration.

Wraps tower/scripts/tower_run.sh and emits tracing + experiment logging.
Tower core remains minimal; this is purely additive.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
ADDONS_DIR = SCRIPT_DIR.parent
TOWER_ROOT = ADDONS_DIR.parent
REPO_ROOT = TOWER_ROOT.parent


def _now_utc() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def _now_epoch_ms() -> int:
    """Get current epoch milliseconds."""
    return int(time.time() * 1000)


def _generate_bridge_id() -> str:
    """Generate unique bridge run ID."""
    ts = _now_utc().strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"bridge_{ts}_{suffix}"


# Input validation
import re

_CARD_ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{1,50}$')
_SESSION_PATTERN = re.compile(r'^[A-Za-z0-9_.-]{1,100}$')
_MODEL_PATTERN = re.compile(r'^[A-Za-z0-9_.:/-]{1,100}$')


def _validate_card_id(card_id: str) -> bool:
    """Validate card_id format (alphanumeric, hyphens, underscores)."""
    return bool(_CARD_ID_PATTERN.match(card_id))


def _validate_session(session: str) -> bool:
    """Validate session name format."""
    return bool(_SESSION_PATTERN.match(session))


def _validate_model(model: str) -> bool:
    """Validate model name format."""
    return bool(_MODEL_PATTERN.match(model))


def _emit_langsmith_local(event: Dict[str, Any]) -> bool:
    """Emit trace to local LangSmith JSONL."""
    try:
        # Try using the adapter
        adapter_path = ADDONS_DIR / "langsmith" / "langsmith_adapter.py"
        if adapter_path.exists():
            sys.path.insert(0, str(adapter_path.parent))
            from langsmith_adapter import emit_trace
            return emit_trace(event)

        # Fallback: write directly to JSONL
        traces_dir = ADDONS_DIR / "langsmith" / "traces"
        traces_dir.mkdir(parents=True, exist_ok=True)

        today = _now_utc().strftime("%Y-%m-%d")
        trace_file = traces_dir / f"{today}.jsonl"

        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str))
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        return True
    except Exception as e:
        print(f"[bridge] LangSmith local trace failed: {e}", file=sys.stderr)
        return False


def _emit_langsmith_remote(event: Dict[str, Any]) -> tuple[bool, bool]:
    """Emit trace to remote LangSmith (if configured)."""
    attempted = False
    ok = True

    enable = os.environ.get("TOWER_LANGSMITH_ENABLE", "0")
    if enable not in ("1", "true", "yes", "on"):
        return attempted, ok

    api_key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if not api_key:
        return attempted, ok

    attempted = True

    try:
        adapter_path = ADDONS_DIR / "langsmith" / "langsmith_adapter.py"
        if adapter_path.exists():
            sys.path.insert(0, str(adapter_path.parent))
            from langsmith_adapter import emit_trace_remote
            ok = emit_trace_remote(event)
        else:
            print("[bridge] LangSmith adapter not found, skipping remote", file=sys.stderr)
            ok = True
    except Exception as e:
        print(f"[bridge] LangSmith remote trace failed: {e}", file=sys.stderr)
        ok = False

    return attempted, ok


def _log_mlflow(
    run_context: Dict[str, Any],
    run_summary: Optional[Dict[str, Any]],
    artifacts_dir: Optional[Path]
) -> tuple[bool, bool]:
    """Log to MLflow (if installed and configured)."""
    attempted = False
    ok = True

    enable = os.environ.get("TOWER_BRIDGE_MLFLOW_ENABLE", "1")
    if enable not in ("1", "true", "yes", "on"):
        return attempted, ok

    try:
        import mlflow
        attempted = True
    except ImportError:
        print("[bridge] SKIPPED mlflow (not installed)", file=sys.stderr)
        return False, True

    try:
        # Set tracking URI
        tracking_uri = os.environ.get(
            "MLFLOW_TRACKING_URI",
            f"file:{ADDONS_DIR / 'mlflow' / 'mlruns'}"
        )
        mlflow.set_tracking_uri(tracking_uri)

        # Set experiment
        experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "tower")
        mlflow.set_experiment(experiment_name)

        # Get run name
        run_name = run_context.get("card_id", "tower_run")

        with mlflow.start_run(run_name=run_name):
            # Log parameters
            mlflow.log_param("card_id", run_context.get("card_id", "unknown"))
            mlflow.log_param("session", run_context.get("session", "unknown"))
            mlflow.log_param("model", run_context.get("model", "unknown"))

            cmd = run_context.get("command", "")
            if len(cmd) > 250:
                cmd = cmd[:250] + "..."
            mlflow.log_param("command", cmd)

            if run_context.get("run_id"):
                mlflow.log_param("tower_run_id", run_context["run_id"])
            if run_context.get("git_sha"):
                mlflow.log_param("git_sha", run_context["git_sha"])
            if run_context.get("spec_version"):
                mlflow.log_param("spec_version", run_context["spec_version"])

            # Log metrics
            if run_summary:
                mlflow.log_metric("exit_code", run_summary.get("exit_code", -1))
                mlflow.log_metric("duration_sec", run_summary.get("duration_seconds", 0))

            # Log artifacts
            if artifacts_dir and artifacts_dir.exists():
                for name in ["run_context.json", "run_summary.json", "stdout.log", "stderr.log"]:
                    artifact_path = artifacts_dir / name
                    if artifact_path.exists():
                        mlflow.log_artifact(str(artifact_path))

        print(f"[bridge] MLflow logged to {tracking_uri}")
        ok = True

    except Exception as e:
        print(f"[bridge] MLflow logging failed: {e}", file=sys.stderr)
        ok = False

    return attempted, ok


def _find_run_directory(
    card_id: str,
    start_time: datetime,
    artifacts_root: Path
) -> Optional[Path]:
    """
    Find the newest run directory for the card created after start_time.

    Checks both UTC date and local date folders since runs may straddle midnight.
    """
    # Get both dates to check
    utc_date = start_time.strftime("%Y-%m-%d")
    local_date = datetime.now().strftime("%Y-%m-%d")
    dates_to_check = list(set([utc_date, local_date]))

    start_epoch = start_time.timestamp()
    candidates = []

    for date_str in dates_to_check:
        date_dir = artifacts_root / date_str / card_id
        if not date_dir.exists():
            continue

        # Look for run_* and review_run_* directories
        for pattern in ["run_*", "review_run_*"]:
            for run_dir in date_dir.glob(pattern):
                if not run_dir.is_dir():
                    continue

                # Check if modified after start time
                try:
                    mtime = run_dir.stat().st_mtime
                    if mtime >= start_epoch:
                        candidates.append((mtime, run_dir))
                except Exception:
                    continue

    if not candidates:
        return None

    # Return newest by mtime
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def run_with_addons(
    card_id: str,
    session: str,
    model: str,
    cmd: str,
    tags: Optional[List[str]] = None,
    note: Optional[str] = None,
    dry_run: bool = False
) -> int:
    """
    Run tower_run.sh with addon tracing and logging.

    Returns the underlying command's exit code.
    Addon failures do NOT affect the exit code.
    """
    bridge_id = _generate_bridge_id()
    start_time = _now_utc()
    start_epoch_ms = _now_epoch_ms()

    # Build tower_run command
    tower_run_script = TOWER_ROOT / "scripts" / "tower_run.sh"

    tower_cmd = [
        "bash", str(tower_run_script),
        "--card", card_id,
        "--session", session,
        "--model", model,
        "--cmd", cmd
    ]

    # Build START event
    start_event = {
        "timestamp": start_time.isoformat(),
        "bridge_id": bridge_id,
        "run_id": None,  # Will be discovered after run
        "card_id": card_id,
        "session": session,
        "model": model,
        "command": cmd,
        "status": "START",
        "tags": tags or [],
        "note": note,
        "addon": {
            "langsmith": {"local": False, "remote_attempted": False, "remote_ok": True},
            "mlflow": {"attempted": False, "ok": True}
        }
    }

    if dry_run:
        print("[bridge] DRY RUN - would execute:")
        print(f"  Command: {' '.join(tower_cmd)}")
        print(f"  Event: {json.dumps(start_event, indent=2)}")
        return 0

    # Emit START trace
    langsmith_enable = os.environ.get("TOWER_BRIDGE_LANGSMITH_ENABLE", "1")
    if langsmith_enable in ("1", "true", "yes", "on"):
        start_event["addon"]["langsmith"]["local"] = _emit_langsmith_local(start_event)
        remote_attempted, remote_ok = _emit_langsmith_remote(start_event)
        start_event["addon"]["langsmith"]["remote_attempted"] = remote_attempted
        start_event["addon"]["langsmith"]["remote_ok"] = remote_ok

    print(f"[bridge] Running: {' '.join(tower_cmd)}")

    # Execute tower_run.sh
    try:
        result = subprocess.run(
            tower_cmd,
            cwd=str(REPO_ROOT),
            timeout=7200  # 2 hours max
        )
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        print("[bridge] ERROR: Command timed out after 2 hours", file=sys.stderr)
        exit_code = -1
    except Exception as e:
        print(f"[bridge] ERROR: Command failed: {e}", file=sys.stderr)
        exit_code = -1

    end_time = _now_utc()
    end_epoch_ms = _now_epoch_ms()
    duration_ms = end_epoch_ms - start_epoch_ms
    duration_sec = duration_ms / 1000.0

    # Find run directory
    artifacts_root = TOWER_ROOT / "artifacts"
    run_dir = _find_run_directory(card_id, start_time, artifacts_root)

    # Load run context and summary
    run_context: Dict[str, Any] = {}
    run_summary: Optional[Dict[str, Any]] = None

    if run_dir:
        context_file = run_dir / "run_context.json"
        summary_file = run_dir / "run_summary.json"

        if context_file.exists():
            try:
                with open(context_file) as f:
                    run_context = json.load(f)
            except Exception:
                pass

        if summary_file.exists():
            try:
                with open(summary_file) as f:
                    run_summary = json.load(f)
            except Exception:
                pass

    # Build END event
    end_event = {
        "timestamp": end_time.isoformat(),
        "bridge_id": bridge_id,
        "run_id": run_context.get("run_id"),
        "card_id": card_id,
        "session": session,
        "model": model,
        "command": cmd,
        "status": "END",
        "exit_code": exit_code,
        "duration_sec": round(duration_sec, 2),
        "paths": [str(run_dir.relative_to(REPO_ROOT))] if run_dir else [],
        "tags": tags or [],
        "note": note,
        "addon": {
            "langsmith": {"local": False, "remote_attempted": False, "remote_ok": True},
            "mlflow": {"attempted": False, "ok": True}
        }
    }

    # Emit END trace
    if langsmith_enable in ("1", "true", "yes", "on"):
        end_event["addon"]["langsmith"]["local"] = _emit_langsmith_local(end_event)
        remote_attempted, remote_ok = _emit_langsmith_remote(end_event)
        end_event["addon"]["langsmith"]["remote_attempted"] = remote_attempted
        end_event["addon"]["langsmith"]["remote_ok"] = remote_ok

    # Log to MLflow
    if run_context or run_summary:
        mlflow_attempted, mlflow_ok = _log_mlflow(run_context, run_summary, run_dir)
        end_event["addon"]["mlflow"]["attempted"] = mlflow_attempted
        end_event["addon"]["mlflow"]["ok"] = mlflow_ok

    # Print summary
    print(f"[bridge] Bridge ID: {bridge_id}")
    print(f"[bridge] Exit code: {exit_code}")
    print(f"[bridge] Duration: {duration_sec:.2f}s")
    if run_dir:
        print(f"[bridge] Run dir: {run_dir}")
    else:
        print("[bridge] WARNING: No run directory found")

    # Return the underlying command's exit code (not addon status)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tower Bridge: Run wrapper with LangSmith + MLflow"
    )
    parser.add_argument("--card", required=True, help="Card ID (e.g., CARD-001)")
    parser.add_argument("--session", required=True, help="Session name")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--cmd", required=True, help="Command to execute")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--note", help="Optional note")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen, don't run")

    args = parser.parse_args()

    # Input validation
    errors = []
    if not _validate_card_id(args.card):
        errors.append(f"Invalid card ID format: {args.card}")
    if not _validate_session(args.session):
        errors.append(f"Invalid session format: {args.session}")
    if not _validate_model(args.model):
        errors.append(f"Invalid model format: {args.model}")

    if errors:
        for err in errors:
            print(f"[bridge] ERROR: {err}", file=sys.stderr)
        return 1

    tags = args.tags.split(",") if args.tags else None

    return run_with_addons(
        card_id=args.card,
        session=args.session,
        model=args.model,
        cmd=args.cmd,
        tags=tags,
        note=args.note,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    sys.exit(main())
