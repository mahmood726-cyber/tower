#!/usr/bin/env python3
"""
Tower LangSmith Tracing Hook

Creates minimal trace records for Tower runs.
By default, only traces metadata (not prompt contents).

Usage:
    python3 tower/scripts/addons/trace_hook.py \\
        --card CARD-XXX \\
        --run_dir <path>
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
    """Load JSON file safely."""
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def write_addon_event(run_dir: Path, card_id: str, run_id: str,
                      status: str, details: dict = None,
                      error_message: str = None, pointers: list = None):
    """Write addon event to run directory."""
    event = {
        "spec_version": SPEC_VERSION,
        "event_type": "TRACE_LINK",
        "timestamp": datetime.now().isoformat(),
        "card_id": card_id,
        "run_id": run_id,
        "addon": "tracing",
        "status": status,
        "schema_validation": "SKIPPED",
        "details": details or {},
        "pointers": pointers or []
    }

    if error_message:
        event["error_message"] = error_message

    event_path = run_dir / "addon_trace_event.json"
    atomic_write_json(event_path, event)
    return event_path


def write_trace_link(run_dir: Path, card_id: str, run_id: str,
                     status: str, reason: str = None, trace_url: str = None):
    """Write trace_link.json to run directory."""
    link = {
        "spec_version": SPEC_VERSION,
        "status": status,
        "card_id": card_id,
        "run_id": run_id,
        "reason": reason,
        "trace_url": trace_url,
        "created_at": datetime.now().isoformat()
    }
    link_path = run_dir / "trace_link.json"
    atomic_write_json(link_path, link)
    return link_path


def main():
    parser = argparse.ArgumentParser(description='Tower LangSmith Tracing Hook')
    parser.add_argument('--card', required=True, help='Card ID')
    parser.add_argument('--run_dir', required=True, help='Path to run directory')

    args = parser.parse_args()

    card_id = args.card
    run_dir = Path(args.run_dir)
    run_id = run_dir.name.replace("run_", "") if run_dir.name.startswith("run_") else None

    tower_root = get_tower_root()
    state_dir = tower_root / "addons" / "tracing" / "state"

    # Check environment configuration
    tracing_enabled = os.environ.get("TOWER_ADDONS_ENABLE_TRACING", "0") == "1"
    api_key = os.environ.get("LANGSMITH_API_KEY", "")
    project = os.environ.get("LANGSMITH_PROJECT", "Tower")
    tracing_mode = os.environ.get("LANGSMITH_TRACING_MODE", "metadata_only")

    if not tracing_enabled:
        print("Tracing disabled (TOWER_ADDONS_ENABLE_TRACING != 1)")
        write_trace_link(run_dir, card_id, run_id, "SKIPPED", reason="tracing disabled")
        write_addon_event(run_dir, card_id, run_id, "SKIPPED",
                          details={"reason": "TOWER_ADDONS_ENABLE_TRACING not set to 1"})
        return 0

    if not api_key:
        print("LangSmith API key not configured")
        write_trace_link(run_dir, card_id, run_id, "SKIPPED", reason="no API key")
        write_addon_event(run_dir, card_id, run_id, "SKIPPED",
                          details={"reason": "LANGSMITH_API_KEY not set"})
        return 0

    # Check if langsmith is installed
    try:
        from langsmith import Client
        HAS_LANGSMITH = True
    except ImportError:
        HAS_LANGSMITH = False

    if not HAS_LANGSMITH:
        print("LangSmith not installed (pip install langsmith)")
        write_trace_link(run_dir, card_id, run_id, "SKIPPED", reason="langsmith not installed")
        write_addon_event(run_dir, card_id, run_id, "NOT_INSTALLED",
                          details={"message": "pip install langsmith to enable tracing"})
        return 0

    # Load run context
    run_context = load_json_safe(run_dir / "run_context.json")
    run_summary = load_json_safe(run_dir / "run_summary.json")

    # Create LangSmith client
    try:
        endpoint = os.environ.get("LANGSMITH_ENDPOINT")
        client = Client(api_key=api_key, api_url=endpoint) if endpoint else Client(api_key=api_key)

        # Create trace metadata (not prompt contents by default)
        trace_metadata = {
            "card_id": card_id,
            "run_id": run_id,
            "spec_version": SPEC_VERSION,
            "model": run_context.get("model"),
            "machine": run_context.get("machine"),
            "session": run_context.get("session"),
            "git_sha": run_context.get("git_sha"),
            "start_time": run_context.get("start_time"),
            "end_time": run_summary.get("end_time"),
            "exit_code": run_summary.get("exit_code"),
            "duration_seconds": run_summary.get("duration_seconds")
        }

        # Create a minimal run in LangSmith
        # Note: Full tracing would require instrumenting the actual LLM calls
        # This just creates a metadata record
        run_data = client.create_run(
            name=f"Tower-{card_id}-{run_id}",
            run_type="chain",
            inputs={"metadata": trace_metadata} if tracing_mode == "metadata_only" else {},
            project_name=project,
            extra={"metadata": trace_metadata}
        )

        trace_url = f"https://smith.langchain.com/projects/{project}/runs/{run_data.id}" if run_data else None

        print(f"Trace created: {trace_url or 'no URL'}")

        write_trace_link(run_dir, card_id, run_id, "OK", trace_url=trace_url)
        write_addon_event(run_dir, card_id, run_id, "OK",
                          details={"trace_url": trace_url, "project": project},
                          pointers=[trace_url] if trace_url else [])

        # Save state
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / f"{run_id or 'unknown'}.json"
        atomic_write_json(state_file, {
            "card_id": card_id,
            "run_id": run_id,
            "trace_url": trace_url,
            "created_at": datetime.now().isoformat()
        })

    except Exception as e:
        print(f"ERROR: Tracing failed: {e}")
        write_trace_link(run_dir, card_id, run_id, "FAILED", reason=str(e))
        write_addon_event(run_dir, card_id, run_id, "FAILED", error_message=str(e))
        # Don't fail the run, just log the error
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
