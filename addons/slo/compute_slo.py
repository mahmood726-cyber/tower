#!/usr/bin/env python3
"""
Tower SLO Computation

Reads Tower metrics and computes SLO status using historical event ledger data.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
TOWER_ROOT = SCRIPT_DIR.parent.parent
CONTROL_DIR = TOWER_ROOT / "control"
LEDGER_DIR = TOWER_ROOT / "addons" / "ledger"

# Import event logger for historical queries
sys.path.insert(0, str(LEDGER_DIR))
try:
    from event_logger import (
        get_state_transitions,
        count_events_by_type,
        get_active_hours,
        read_events,
    )
    LEDGER_AVAILABLE = True
except ImportError:
    LEDGER_AVAILABLE = False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_run_id() -> str:
    ts = _now_utc().strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{ts}_{suffix}"


def _load_json(path: Path) -> Optional[Dict]:
    """Load JSON file or return None."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _load_config() -> Dict:
    """Load SLO config."""
    config_path = SCRIPT_DIR / "slo_config.json"
    config = _load_json(config_path)
    if config:
        return config

    # Default config
    return {
        "spec_version": "v1.5.5",
        "default_window_days": 30,
        "thresholds": {
            "rollback_rate_monthly_pct": {"target": 3, "breach": 5},
            "validator_fail_rate_pct": {"target": 15, "breach": 25},
            "glm_pass_audit_disagreement_pct": {"target": 10, "breach": 15},
            "drift_incidents_per_100_active_hours": {"target": 2, "breach": 4}
        }
    }


def _load_metrics_csv() -> List[Dict]:
    """Load metrics from CSV."""
    metrics_path = CONTROL_DIR / "metrics.csv"
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


def _compute_slo_metric(
    metric_name: str,
    value: Optional[float],
    threshold: Dict
) -> Dict:
    """Compute SLO status for a single metric."""
    target = threshold.get("target", 0)
    breach = threshold.get("breach", 0)

    if value is None:
        return {
            "value": None,
            "target": target,
            "breach": breach,
            "status": "UNKNOWN"
        }

    if value >= breach:
        status = "BREACH"
    elif value >= target:
        status = "WARN"
    else:
        status = "OK"

    return {
        "value": round(value, 2),
        "target": target,
        "breach": breach,
        "status": status
    }


def _compute_rollback_rate_from_ledger(since: str, notes: List[str]) -> Optional[float]:
    """Compute rollback rate from historical ledger data."""
    if not LEDGER_AVAILABLE:
        notes.append("Event ledger not available for historical rollback computation")
        return None

    try:
        transitions = get_state_transitions(since=since)
        if not transitions:
            notes.append("No state transitions found in ledger for rollback rate")
            return None

        # Count unique cards that had state changes
        card_ids = set(t["card_id"] for t in transitions if t.get("card_id"))
        if not card_ids:
            return None

        # Count cards that transitioned to ROLLED_BACK
        rolled_back_cards = set(
            t["card_id"] for t in transitions
            if t.get("to_state") == "ROLLED_BACK" and t.get("card_id")
        )

        return (len(rolled_back_cards) / len(card_ids)) * 100
    except Exception as e:
        notes.append(f"Error computing historical rollback rate: {e}")
        return None


def _compute_validator_fail_rate_from_ledger(since: str, notes: List[str]) -> Optional[float]:
    """Compute validator fail rate from historical ledger data."""
    if not LEDGER_AVAILABLE:
        notes.append("Event ledger not available for historical validation computation")
        return None

    try:
        # Count validation events
        total_validations = count_events_by_type("validation.*", since=since)
        failed_validations = count_events_by_type("validation.failed", since=since)

        if total_validations == 0:
            notes.append("No validation events found in ledger")
            return None

        return (failed_validations / total_validations) * 100
    except Exception as e:
        notes.append(f"Error computing historical validation rate: {e}")
        return None


def _compute_drift_rate_from_ledger(since: str, notes: List[str]) -> Optional[float]:
    """Compute drift incidents per 100 active hours from ledger."""
    if not LEDGER_AVAILABLE:
        notes.append("Event ledger not available for historical drift computation")
        return None

    try:
        # Count drift events
        drift_count = count_events_by_type("drift.*", since=since)

        # Get actual active hours from ledger
        active_hours = get_active_hours(since=since)

        if active_hours < 1.0:
            notes.append("Insufficient active hours for drift rate computation")
            return None

        # Normalize to per 100 active hours
        return (drift_count / active_hours) * 100
    except Exception as e:
        notes.append(f"Error computing historical drift rate: {e}")
        return None


def compute_slo(write_output: bool = False) -> Dict:
    """
    Compute SLO status from Tower metrics.

    Uses historical event ledger data when available for accurate
    time-windowed metrics. Falls back to current state when ledger
    is not available.

    Returns SLO status dict.
    """
    config = _load_config()
    thresholds = config.get("thresholds", {})
    window_days = config.get("default_window_days", 30)

    # Calculate time window
    now = _now_utc()
    since_dt = now - timedelta(days=window_days)
    since = since_dt.isoformat()

    # Load data sources for fallback
    status = _load_json(CONTROL_DIR / "status.json")
    metrics_rows = _load_metrics_csv()
    drift_alerts = _load_json(CONTROL_DIR / "alerts" / "drift_alerts.json")

    notes = []

    # Indicate data source
    if LEDGER_AVAILABLE:
        notes.append(f"Using historical ledger data (window: {window_days} days)")
    else:
        notes.append("Using current state fallback (ledger not available)")

    # Compute metrics
    metrics_results = {}

    # Rollback rate - prefer historical ledger data
    rollback_value = _compute_rollback_rate_from_ledger(since, notes)

    # Fallback to current state if ledger computation failed
    if rollback_value is None and status:
        cards = status.get("cards", {})
        total_cards = len(cards)
        rolled_back = sum(
            1 for c in cards.values()
            if c.get("state") == "ROLLED_BACK"
        )
        if total_cards > 0:
            rollback_value = (rolled_back / total_cards) * 100
            notes.append("Rollback rate: using current state fallback")
        else:
            notes.append("No cards found for rollback rate")
    elif rollback_value is None and not status:
        notes.append("status.json not found")

    metrics_results["rollback_rate_monthly_pct"] = _compute_slo_metric(
        "rollback_rate_monthly_pct",
        rollback_value,
        thresholds.get("rollback_rate_monthly_pct", {"target": 3, "breach": 5})
    )

    # Validator fail rate - prefer historical ledger data
    validator_value = _compute_validator_fail_rate_from_ledger(since, notes)

    # Fallback to current state if ledger computation failed
    if validator_value is None and status:
        cards = status.get("cards", {})
        total_reviews = 0
        failed_reviews = 0
        for c in cards.values():
            if c.get("state") in ("REVIEW_PENDING", "GREEN", "MERGED", "ESCALATED"):
                total_reviews += 1
            if c.get("state") == "ESCALATED":
                failed_reviews += 1
        if total_reviews > 0:
            validator_value = (failed_reviews / total_reviews) * 100
            notes.append("Validator rate: using current state fallback")

    metrics_results["validator_fail_rate_pct"] = _compute_slo_metric(
        "validator_fail_rate_pct",
        validator_value,
        thresholds.get("validator_fail_rate_pct", {"target": 15, "breach": 25})
    )

    # GLM pass/audit disagreement - placeholder
    glm_value = None
    notes.append("GLM audit data not yet available")

    metrics_results["glm_pass_audit_disagreement_pct"] = _compute_slo_metric(
        "glm_pass_audit_disagreement_pct",
        glm_value,
        thresholds.get("glm_pass_audit_disagreement_pct", {"target": 10, "breach": 15})
    )

    # Drift incidents - prefer historical ledger data with actual active hours
    drift_value = _compute_drift_rate_from_ledger(since, notes)

    # Fallback to alerts file if ledger computation failed
    if drift_value is None and drift_alerts:
        alerts = drift_alerts.get("alerts", [])
        drift_count = len(alerts)
        # Try to get active hours from ledger even if other queries failed
        active_hours = 100.0  # Default assumption
        if LEDGER_AVAILABLE:
            try:
                ledger_hours = get_active_hours(since=since)
                if ledger_hours >= 1.0:
                    active_hours = ledger_hours
            except Exception:
                pass
        drift_value = (drift_count / active_hours) * 100
        notes.append(f"Drift rate: using alerts file (active hours: {active_hours:.1f})")
    elif drift_value is None:
        notes.append("drift_alerts.json not found")

    metrics_results["drift_incidents_per_100_active_hours"] = _compute_slo_metric(
        "drift_incidents_per_100_active_hours",
        drift_value,
        thresholds.get("drift_incidents_per_100_active_hours", {"target": 2, "breach": 4})
    )

    # Compute overall status
    statuses = [m["status"] for m in metrics_results.values()]
    if "BREACH" in statuses:
        overall_status = "BREACH"
    elif "WARN" in statuses:
        overall_status = "WARN"
    elif all(s == "OK" for s in statuses):
        overall_status = "OK"
    else:
        overall_status = "UNKNOWN"

    # Build result
    result = {
        "spec_version": config.get("spec_version", "v1.5.5"),
        "last_updated": _now_utc().isoformat(),
        "overall_status": overall_status,
        "metrics": metrics_results,
        "window_days": window_days,
        "notes": notes
    }

    if write_output:
        _write_outputs(result, config)

    return result


def _write_outputs(result: Dict, config: Dict):
    """Write SLO outputs atomically."""
    run_id = _generate_run_id()
    today = _now_utc().strftime("%Y-%m-%d")

    # Ensure directories
    (CONTROL_DIR / "alerts").mkdir(parents=True, exist_ok=True)
    artifacts_today = ARTIFACTS_DIR / today
    artifacts_today.mkdir(parents=True, exist_ok=True)

    # Write slo_status.json
    status_file = CONTROL_DIR / "slo_status.json"
    tmp_file = status_file.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(result, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, status_file)
    print(f"Wrote: {status_file}")

    # Write breaches if any
    breaches = [
        (name, m) for name, m in result["metrics"].items()
        if m["status"] == "BREACH"
    ]

    if breaches:
        breaches_file = CONTROL_DIR / "alerts" / "slo_breaches.json"
        breach_data = {
            "spec_version": result["spec_version"],
            "created_at": result["last_updated"],
            "breaches": [
                {"metric": name, "value": m["value"], "breach_threshold": m["breach"]}
                for name, m in breaches
            ]
        }
        tmp_file = breaches_file.with_suffix(".tmp")
        with open(tmp_file, "w") as f:
            json.dump(breach_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, breaches_file)
        print(f"Wrote: {breaches_file}")

    # Write markdown report
    report_file = artifacts_today / f"slo_report_{run_id}.md"
    report = _generate_report(result)
    with open(report_file, "w") as f:
        f.write(report)
    print(f"Wrote: {report_file}")


def _generate_report(result: Dict) -> str:
    """Generate markdown report."""
    lines = [
        "# SLO Status Report",
        "",
        f"**Generated:** {result['last_updated']}",
        f"**Window:** {result['window_days']} days",
        f"**Overall Status:** {result['overall_status']}",
        "",
        "## Metrics",
        "",
        "| Metric | Value | Target | Breach | Status |",
        "|--------|-------|--------|--------|--------|"
    ]

    for name, m in result["metrics"].items():
        value = m["value"] if m["value"] is not None else "N/A"
        lines.append(
            f"| {name} | {value} | {m['target']} | {m['breach']} | {m['status']} |"
        )

    lines.extend([
        "",
        "## Notes",
        ""
    ])

    for note in result.get("notes", []):
        lines.append(f"- {note}")

    lines.extend([
        "",
        "---",
        "*Generated by Tower SLO Addon*"
    ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tower SLO Computation")
    parser.add_argument("--write", action="store_true",
                        help="Write output files")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON to stdout")

    args = parser.parse_args()

    result = compute_slo(write_output=args.write)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Overall SLO Status: {result['overall_status']}")
        for name, m in result["metrics"].items():
            value = m["value"] if m["value"] is not None else "N/A"
            print(f"  {name}: {value} ({m['status']})")

    # Exit non-zero on breach
    if result["overall_status"] == "BREACH":
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
