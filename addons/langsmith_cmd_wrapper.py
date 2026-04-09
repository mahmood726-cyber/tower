#!/usr/bin/env python3
"""
langsmith_cmd_wrapper.py

Wrap an arbitrary command so it can be traced IF your environment is already configured
(LANGSMITH_TRACING=true, LANGSMITH_API_KEY set, LANGSMITH_PROJECT set).

No secrets are stored here. This file does not start any service.

Usage:
  python tower/addons/langsmith_cmd_wrapper.py --name "tower_validate" -- bash tower/scripts/validate_all.sh
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="tower_cmd", help="Trace/run name label")
    ap.add_argument("--project", default="", help="Optional: override LANGSMITH_PROJECT")
    ap.add_argument("--", dest="sep", action="store_true", help="Separator before command")
    ap.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to execute after --")
    args = ap.parse_args()

    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("ERROR: no command provided. Example: -- bash tower/scripts/validate_all.sh")
        return 2

    # Optional overrides (do not require secrets)
    if args.project.strip():
        os.environ["LANGSMITH_PROJECT"] = args.project.strip()

    # Make it easy to see if tracing is on
    tracing = os.environ.get("LANGSMITH_TRACING", "").lower() in ("1", "true", "yes", "on")
    project = os.environ.get("LANGSMITH_PROJECT", "")
    has_key = bool(os.environ.get("LANGSMITH_API_KEY", "").strip())

    print(f"[tower-addons] name={args.name} tracing={tracing} project={project} api_key_set={has_key}")
    print(f"[tower-addons] start={datetime.utcnow().isoformat()}Z")
    print(f"+ {' '.join(cmd)}")

    # Best-effort: if langsmith is installed, import it so SDK hooks can attach (no hard dependency).
    try:
        import langsmith  # type: ignore  # noqa: F401
    except Exception:
        pass

    p = subprocess.run(cmd)
    rc = int(p.returncode)
    print(f"[tower-addons] end rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
