#!/usr/bin/env python3
"""
CLI for emitting local LangSmith traces.

Usage:
    python3 tower/addons/langsmith/trace_local.py --event '{"run_id":"...","status":"START"}'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Import from sibling module
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from langsmith_adapter import emit_trace, emit_trace_remote


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit a trace event to local JSONL file"
    )
    parser.add_argument(
        "--event",
        required=True,
        help="JSON string with event data"
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Also attempt remote trace (if configured)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output on success"
    )

    args = parser.parse_args()

    # Parse event JSON
    try:
        event = json.loads(args.event)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
        return 1

    if not isinstance(event, dict):
        print("ERROR: Event must be a JSON object", file=sys.stderr)
        return 1

    # Emit local trace
    local_ok = emit_trace(event)
    if not local_ok:
        print("ERROR: Local trace failed", file=sys.stderr)
        return 1

    # Optionally emit remote trace
    remote_ok = True
    if args.remote:
        remote_ok = emit_trace_remote(event)

    if not args.quiet:
        print(f"[trace_local] local=OK remote_attempted={args.remote} remote_ok={remote_ok}")

    return 0 if (local_ok and remote_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
