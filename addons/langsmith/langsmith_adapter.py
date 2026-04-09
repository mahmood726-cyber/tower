#!/usr/bin/env python3
"""
LangSmith Adapter for Tower

Provides local trace logging with optional remote LangSmith integration.
Local traces always work; remote requires langsmith package + API key.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Determine paths
SCRIPT_DIR = Path(__file__).parent.resolve()
TRACES_DIR = SCRIPT_DIR / "traces"


def _ensure_traces_dir() -> Path:
    """Ensure traces directory exists."""
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    return TRACES_DIR


def _get_today_file() -> Path:
    """Get today's trace file path."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _ensure_traces_dir() / f"{today}.jsonl"


def _normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Add timestamp if missing."""
    if "timestamp" not in event:
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event


def emit_trace(event: Dict[str, Any]) -> bool:
    """
    Emit a trace event to local JSONL file.

    Always writes locally. Never fails the caller.

    Args:
        event: Dictionary with trace data

    Returns:
        True if write succeeded, False otherwise
    """
    try:
        event = _normalize_event(event)
        trace_file = _get_today_file()

        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str))
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        return True
    except Exception as e:
        print(f"[langsmith_adapter] local trace failed: {e}", flush=True)
        return False


def emit_trace_remote(event: Dict[str, Any]) -> bool:
    """
    Emit a trace event to remote LangSmith (if configured).

    Only sends if:
    - TOWER_LANGSMITH_ENABLE=1
    - LANGSMITH_API_KEY is set
    - langsmith package is installed

    Args:
        event: Dictionary with trace data

    Returns:
        True if sent successfully or skipped (not enabled), False on error
    """
    # Check if remote tracing is enabled
    enable = os.environ.get("TOWER_LANGSMITH_ENABLE", "0")
    if enable not in ("1", "true", "yes", "on"):
        return True  # Not enabled, not an error

    api_key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if not api_key:
        print("[langsmith_adapter] remote skipped: LANGSMITH_API_KEY not set", flush=True)
        return True  # Not configured, not an error

    try:
        import langsmith
        from langsmith import Client

        project = os.environ.get("LANGSMITH_PROJECT", "tower")
        endpoint = os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

        client = Client(api_key=api_key, api_url=endpoint)

        event = _normalize_event(event)

        # Create a minimal run record
        run_id = event.get("run_id", f"tower_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")

        # Log as a simple run
        client.create_run(
            name=event.get("command", "tower_trace"),
            run_type="chain",
            project_name=project,
            inputs={"event": event},
            outputs={"status": event.get("status", "INFO")},
            tags=event.get("tags", []),
            extra={"metadata": event}
        )

        return True

    except ImportError:
        print("[langsmith_adapter] remote skipped: pip install langsmith", flush=True)
        return True  # Not installed, not an error
    except Exception as e:
        print(f"[langsmith_adapter] remote trace failed: {e}", flush=True)
        return False


def get_local_traces(date: Optional[str] = None, limit: int = 100) -> list:
    """
    Read local traces for a given date.

    Args:
        date: Date string (YYYY-MM-DD) or None for today
        limit: Maximum number of traces to return

    Returns:
        List of trace events (newest first)
    """
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    trace_file = TRACES_DIR / f"{date}.jsonl"

    if not trace_file.exists():
        return []

    traces = []
    try:
        with open(trace_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        traces.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return []

    # Return newest first, limited
    return list(reversed(traces[-limit:]))


if __name__ == "__main__":
    # Quick test
    test_event = {
        "run_id": "test_run",
        "status": "INFO",
        "message": "adapter self-test"
    }

    local_ok = emit_trace(test_event)
    remote_ok = emit_trace_remote(test_event)

    print(f"[langsmith_adapter] self-test: local={local_ok} remote_attempted={remote_ok}")
