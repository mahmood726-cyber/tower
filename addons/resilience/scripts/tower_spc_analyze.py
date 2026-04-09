#!/usr/bin/env python3
"""
Tower SPC Analysis

Statistical Process Control analysis for Tower metrics.
Uses individuals/moving range charts with 3-sigma control limits.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
RESILIENCE_DIR = SCRIPT_DIR.parent
TOWER_ROOT = RESILIENCE_DIR.parent.parent
CONTROL_DIR = TOWER_ROOT / "control"
SPC_DIR = RESILIENCE_DIR / "spc"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _load_metrics(metrics_path: Path) -> List[Dict]:
    """Load metrics from CSV."""
    if not metrics_path.exists():
        return []

    rows = []
    try:
        with open(metrics_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        pass

    return rows


def _calculate_control_limits(
    values: List[float],
    baseline_n: int = 30
) -> Tuple[float, float, float, float]:
    """
    Calculate control limits using individuals/moving range method.

    Returns: (centerline, lcl, ucl, sigma_estimate)
    """
    if len(values) < 2:
        return 0, 0, 0, 0

    # Use baseline (first N points) or all if fewer
    baseline = values[:min(baseline_n, len(values))]

    # Centerline is mean
    centerline = sum(baseline) / len(baseline)

    # Moving ranges
    moving_ranges = []
    for i in range(1, len(baseline)):
        mr = abs(baseline[i] - baseline[i - 1])
        moving_ranges.append(mr)

    if not moving_ranges:
        return centerline, centerline, centerline, 0

    # Average moving range
    mr_bar = sum(moving_ranges) / len(moving_ranges)

    # Sigma estimate: MRbar / d2 where d2 = 1.128 for n=2
    d2 = 1.128
    sigma_estimate = mr_bar / d2

    # Control limits: 3 sigma
    lcl = centerline - 3 * sigma_estimate
    ucl = centerline + 3 * sigma_estimate

    return centerline, lcl, ucl, sigma_estimate


def _detect_anomalies(
    values: List[float],
    centerline: float,
    lcl: float,
    ucl: float,
    sigma: float
) -> List[Dict]:
    """
    Detect SPC rule violations.

    Rules:
    - Point outside 3-sigma (UCL/LCL)
    - 2 of last 3 beyond 2-sigma
    - 4 of last 5 beyond 1-sigma
    """
    alerts = []

    if sigma <= 0 or len(values) < 3:
        return alerts

    for i, value in enumerate(values):
        # Rule 1: Beyond 3-sigma
        if value > ucl or value < lcl:
            alerts.append({
                "index": i,
                "rule": "outside_3sigma",
                "value": value,
                "severity": "high",
                "description": f"Value {value:.2f} outside control limits [{lcl:.2f}, {ucl:.2f}]"
            })

        # Rule 2: 2 of last 3 beyond 2-sigma
        if i >= 2:
            two_sigma_upper = centerline + 2 * sigma
            two_sigma_lower = centerline - 2 * sigma
            last_3 = values[i - 2:i + 1]
            outside_2sigma = sum(
                1 for v in last_3
                if v > two_sigma_upper or v < two_sigma_lower
            )
            if outside_2sigma >= 2:
                alerts.append({
                    "index": i,
                    "rule": "2_of_3_beyond_2sigma",
                    "value": value,
                    "severity": "medium",
                    "description": f"2 of last 3 points beyond 2-sigma"
                })

        # Rule 3: 4 of last 5 beyond 1-sigma
        if i >= 4:
            one_sigma_upper = centerline + sigma
            one_sigma_lower = centerline - sigma
            last_5 = values[i - 4:i + 1]
            outside_1sigma = sum(
                1 for v in last_5
                if v > one_sigma_upper or v < one_sigma_lower
            )
            if outside_1sigma >= 4:
                alerts.append({
                    "index": i,
                    "rule": "4_of_5_beyond_1sigma",
                    "value": value,
                    "severity": "low",
                    "description": f"4 of last 5 points beyond 1-sigma"
                })

    return alerts


def analyze_spc(metrics_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Perform SPC analysis on Tower metrics.

    Returns analysis results dict.
    """
    if metrics_path is None:
        metrics_path = CONTROL_DIR / "metrics.csv"

    metrics = _load_metrics(metrics_path)

    result = {
        "spec_version": "v1.5.5",
        "analyzed_at": _now_utc().isoformat(),
        "metrics_file": str(metrics_path),
        "data_points": len(metrics),
        "analyses": {},
        "alerts": []
    }

    if not metrics:
        result["notes"] = ["No metrics data available"]
        return result

    # Analyze numeric columns
    numeric_columns = []
    for col in metrics[0].keys():
        if col.lower() in ("timestamp", "date", "time", "card_id", "run_id"):
            continue
        # Try to parse as float
        try:
            float(metrics[0][col])
            numeric_columns.append(col)
        except (ValueError, TypeError):
            pass

    for col in numeric_columns:
        values = []
        for row in metrics:
            try:
                values.append(float(row[col]))
            except (ValueError, TypeError):
                continue

        if len(values) < 5:
            continue

        centerline, lcl, ucl, sigma = _calculate_control_limits(values)
        alerts = _detect_anomalies(values, centerline, lcl, ucl, sigma)

        result["analyses"][col] = {
            "data_points": len(values),
            "centerline": round(centerline, 4),
            "lcl": round(lcl, 4),
            "ucl": round(ucl, 4),
            "sigma": round(sigma, 4),
            "latest_value": round(values[-1], 4) if values else None,
            "alert_count": len(alerts)
        }

        # Add alerts with column context
        for alert in alerts:
            alert["metric"] = col
            result["alerts"].append(alert)

    return result


def write_outputs(result: Dict[str, Any]):
    """Write SPC outputs."""
    # Ensure directories
    SPC_DIR.mkdir(parents=True, exist_ok=True)
    (CONTROL_DIR / "alerts").mkdir(parents=True, exist_ok=True)

    # Write SPC report
    report_file = SPC_DIR / "spc_report.md"
    report = _generate_report(result)
    with open(report_file, "w") as f:
        f.write(report)
    print(f"Wrote: {report_file}")

    # Write alerts JSON
    alerts_file = CONTROL_DIR / "alerts" / "spc_alerts.json"
    alerts_data = {
        "spec_version": "v1.5.5",
        "created_at": result["analyzed_at"],
        "alert_count": len(result["alerts"]),
        "alerts": result["alerts"]
    }

    tmp_file = alerts_file.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(alerts_data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, alerts_file)
    print(f"Wrote: {alerts_file}")


def _generate_report(result: Dict[str, Any]) -> str:
    """Generate markdown SPC report."""
    lines = [
        "# SPC Analysis Report",
        "",
        f"**Generated:** {result['analyzed_at']}",
        f"**Data Points:** {result['data_points']}",
        f"**Metrics File:** {result['metrics_file']}",
        "",
        "## Control Charts",
        ""
    ]

    if not result["analyses"]:
        lines.append("No data available for analysis.")
    else:
        lines.extend([
            "| Metric | Points | Centerline | LCL | UCL | Latest | Alerts |",
            "|--------|--------|------------|-----|-----|--------|--------|"
        ])

        for metric, analysis in result["analyses"].items():
            lines.append(
                f"| {metric} | {analysis['data_points']} | "
                f"{analysis['centerline']:.2f} | {analysis['lcl']:.2f} | "
                f"{analysis['ucl']:.2f} | {analysis['latest_value']:.2f} | "
                f"{analysis['alert_count']} |"
            )

    lines.extend([
        "",
        "## Alerts",
        ""
    ])

    if not result["alerts"]:
        lines.append("No alerts detected.")
    else:
        for alert in result["alerts"]:
            severity = alert.get("severity", "unknown").upper()
            lines.append(f"- **[{severity}]** {alert['metric']}: {alert['description']}")

    lines.extend([
        "",
        "## Methodology",
        "",
        "Using individuals/moving range (I-MR) chart methodology:",
        "- Centerline: Mean of baseline data",
        "- Sigma estimate: MRbar / 1.128",
        "- Control limits: Centerline +/- 3*sigma",
        "",
        "Alert rules:",
        "1. Point outside 3-sigma (HIGH)",
        "2. 2 of last 3 beyond 2-sigma (MEDIUM)",
        "3. 4 of last 5 beyond 1-sigma (LOW)",
        "",
        "---",
        "*Tower SPC Analysis v1.5.5*"
    ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tower SPC Analysis")
    parser.add_argument("--metrics", help="Path to metrics CSV")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    parser.add_argument("--write", action="store_true", help="Write output files")

    args = parser.parse_args()

    metrics_path = Path(args.metrics) if args.metrics else None
    result = analyze_spc(metrics_path)

    if args.json:
        print(json.dumps(result, indent=2))
    elif args.write:
        write_outputs(result)
    else:
        print(f"SPC Analysis: {result['data_points']} data points")
        print(f"Metrics analyzed: {len(result['analyses'])}")
        print(f"Alerts: {len(result['alerts'])}")

        if result["alerts"]:
            print("\nTop alerts:")
            for alert in result["alerts"][:5]:
                print(f"  [{alert['severity'].upper()}] {alert['metric']}: {alert['description']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
