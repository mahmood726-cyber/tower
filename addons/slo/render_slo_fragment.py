#!/usr/bin/env python3
"""
Render SLO Dashboard Fragment

Generates HTML fragment from slo_status.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
TOWER_ROOT = SCRIPT_DIR.parent.parent
CONTROL_DIR = TOWER_ROOT / "control"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_run_id() -> str:
    ts = _now_utc().strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{ts}_{suffix}"


def _load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _status_color(status: str) -> str:
    """Get color for status."""
    colors = {
        "OK": "#28a745",
        "WARN": "#ffc107",
        "BREACH": "#dc3545",
        "UNKNOWN": "#6c757d"
    }
    return colors.get(status, "#6c757d")


def render_fragment() -> str:
    """Generate HTML fragment for SLO status."""
    slo_status = _load_json(CONTROL_DIR / "slo_status.json")

    if not slo_status:
        return """
<div class="slo-fragment">
  <h3>SLO Status</h3>
  <p style="color: #6c757d;">No SLO data available. Run compute_slo.py first.</p>
</div>
"""

    overall = slo_status.get("overall_status", "UNKNOWN")
    overall_color = _status_color(overall)
    last_updated = slo_status.get("last_updated", "Unknown")
    window_days = slo_status.get("window_days", 30)

    # Build metrics table
    rows = []
    for name, m in slo_status.get("metrics", {}).items():
        value = m.get("value")
        value_str = f"{value:.2f}" if value is not None else "N/A"
        target = m.get("target", "N/A")
        status = m.get("status", "UNKNOWN")
        color = _status_color(status)

        rows.append(f"""
      <tr>
        <td>{name}</td>
        <td>{value_str}</td>
        <td>{target}</td>
        <td style="color: {color}; font-weight: bold;">{status}</td>
      </tr>""")

    metrics_html = "\n".join(rows) if rows else "<tr><td colspan='4'>No metrics</td></tr>"

    return f"""
<div class="slo-fragment" style="font-family: sans-serif; padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin: 10px 0;">
  <h3 style="margin-top: 0;">SLO Status: <span style="color: {overall_color};">{overall}</span></h3>
  <p style="font-size: 0.9em; color: #666;">
    Last updated: {last_updated} | Window: {window_days} days
  </p>
  <table style="width: 100%; border-collapse: collapse; font-size: 0.9em;">
    <thead>
      <tr style="background: #f5f5f5;">
        <th style="text-align: left; padding: 8px; border-bottom: 1px solid #ddd;">Metric</th>
        <th style="text-align: left; padding: 8px; border-bottom: 1px solid #ddd;">Value</th>
        <th style="text-align: left; padding: 8px; border-bottom: 1px solid #ddd;">Target</th>
        <th style="text-align: left; padding: 8px; border-bottom: 1px solid #ddd;">Status</th>
      </tr>
    </thead>
    <tbody>
      {metrics_html}
    </tbody>
  </table>
</div>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render SLO Dashboard Fragment")
    parser.add_argument("--stdout", action="store_true",
                        help="Output to stdout instead of file")

    args = parser.parse_args()

    fragment = render_fragment()

    if args.stdout:
        print(fragment)
    else:
        run_id = _generate_run_id()
        today = _now_utc().strftime("%Y-%m-%d")
        output_dir = ARTIFACTS_DIR / today
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"slo_fragment_{run_id}.html"
        with open(output_file, "w") as f:
            f.write(fragment)

        print(f"Wrote: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
