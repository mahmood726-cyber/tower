#!/usr/bin/env python3
"""
Tower Error Budget Update

Updates error budget status based on SLO configuration.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
RESILIENCE_DIR = SCRIPT_DIR.parent
TOWER_ROOT = RESILIENCE_DIR.parent.parent
CONTROL_DIR = TOWER_ROOT / "control"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _load_json(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _write_json_atomic(path: Path, data: Dict):
    """Write JSON atomically with fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = path.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, path)


def _get_default_slo_config() -> Dict:
    """Default SLO configuration."""
    return {
        "spec_version": "v1.5.5",
        "window_days": 30,
        "slos": {
            "rollback_rate_monthly_pct": {
                "target": 3,
                "freeze": 5,
                "description": "Monthly rollback rate"
            },
            "validator_fail_review_pending_pct": {
                "target": 15,
                "freeze": 25,
                "description": "Validator failure rate"
            },
            "reviewer_disagreement_pct": {
                "target": 10,
                "freeze": 15,
                "description": "Reviewer disagreement rate"
            },
            "drift_incidents_per_100_active_hours": {
                "target": 2,
                "freeze": 4,
                "description": "Drift incidents per 100 active hours"
            }
        }
    }


def compute_error_budget() -> Dict[str, Any]:
    """
    Compute error budget status.

    Returns error budget status dict.
    """
    # Load SLO config
    config_path = CONTROL_DIR / "slo_config.json"
    config = _load_json(config_path)
    if not config:
        config = _get_default_slo_config()

    # Load status for card counts
    status = _load_json(CONTROL_DIR / "status.json")

    # Load drift alerts
    drift_alerts = _load_json(CONTROL_DIR / "alerts" / "drift_alerts.json")

    window_days = config.get("window_days", 30)
    slos = config.get("slos", _get_default_slo_config()["slos"])

    result = {
        "spec_version": "v1.5.5",
        "last_updated": _now_utc().isoformat(),
        "window_days": window_days,
        "overall_status": "UNKNOWN",
        "slo_statuses": {},
        "freeze_triggered": False,
        "freeze_reasons": []
    }

    # Calculate each SLO
    # Rollback rate
    rollback_value = None
    if status:
        cards = status.get("cards", {})
        total = len(cards)
        rolled_back = sum(1 for c in cards.values() if c.get("state") == "ROLLED_BACK")
        if total > 0:
            rollback_value = (rolled_back / total) * 100

    slo_def = slos.get("rollback_rate_monthly_pct", {"target": 3, "freeze": 5})
    result["slo_statuses"]["rollback_rate_monthly_pct"] = _evaluate_slo(
        rollback_value, slo_def
    )

    # Validator fail rate (estimate from ESCALATED)
    validator_value = None
    if status:
        cards = status.get("cards", {})
        reviewed = sum(1 for c in cards.values() if c.get("state") in
                       ("REVIEW_PENDING", "GREEN", "MERGED", "ESCALATED"))
        escalated = sum(1 for c in cards.values() if c.get("state") == "ESCALATED")
        if reviewed > 0:
            validator_value = (escalated / reviewed) * 100

    slo_def = slos.get("validator_fail_review_pending_pct", {"target": 15, "freeze": 25})
    result["slo_statuses"]["validator_fail_review_pending_pct"] = _evaluate_slo(
        validator_value, slo_def
    )

    # Reviewer disagreement (placeholder)
    slo_def = slos.get("reviewer_disagreement_pct", {"target": 10, "freeze": 15})
    result["slo_statuses"]["reviewer_disagreement_pct"] = _evaluate_slo(
        None, slo_def
    )

    # Drift incidents
    drift_value = None
    if drift_alerts:
        alerts = drift_alerts.get("alerts", [])
        drift_value = len(alerts)

    slo_def = slos.get("drift_incidents_per_100_active_hours", {"target": 2, "freeze": 4})
    result["slo_statuses"]["drift_incidents_per_100_active_hours"] = _evaluate_slo(
        drift_value, slo_def
    )

    # Determine overall status
    statuses = [s["status"] for s in result["slo_statuses"].values()]

    if "FREEZE" in statuses:
        result["overall_status"] = "FREEZE"
        result["freeze_triggered"] = True
        for name, slo_status in result["slo_statuses"].items():
            if slo_status["status"] == "FREEZE":
                result["freeze_reasons"].append(f"{name} exceeded freeze threshold")
    elif "WARN" in statuses:
        result["overall_status"] = "WARN"
    elif all(s == "OK" for s in statuses):
        result["overall_status"] = "OK"
    else:
        result["overall_status"] = "UNKNOWN"

    return result


def _evaluate_slo(value: Optional[float], slo_def: Dict) -> Dict:
    """Evaluate single SLO."""
    target = slo_def.get("target", 0)
    freeze = slo_def.get("freeze", 0)

    if value is None:
        return {
            "value": None,
            "target": target,
            "freeze_threshold": freeze,
            "status": "UNKNOWN"
        }

    if value >= freeze:
        status = "FREEZE"
    elif value >= target:
        status = "WARN"
    else:
        status = "OK"

    return {
        "value": round(value, 2),
        "target": target,
        "freeze_threshold": freeze,
        "status": status
    }


def update_error_budget():
    """Update error budget files."""
    result = compute_error_budget()

    # Write error_budget_status.json
    status_file = CONTROL_DIR / "error_budget_status.json"
    _write_json_atomic(status_file, result)
    print(f"Wrote: {status_file}")

    # Write merge_freeze.json if freeze triggered
    freeze_file = CONTROL_DIR / "merge_freeze.json"

    if result["freeze_triggered"]:
        freeze_data = {
            "spec_version": "v1.5.5",
            "freeze_enabled": True,
            "status": "ON",
            "reason": "; ".join(result["freeze_reasons"]),
            "created_at": result["last_updated"],
            "until": (_now_utc() + timedelta(hours=24)).isoformat()
        }
        _write_json_atomic(freeze_file, freeze_data)
        print(f"Wrote: {freeze_file} (FREEZE ENABLED)")
    else:
        # Clear freeze if it exists and was auto-created
        if freeze_file.exists():
            existing = _load_json(freeze_file)
            if existing and existing.get("spec_version") == "v1.5.5":
                # Only clear if it was our freeze
                freeze_data = {
                    "spec_version": "v1.5.5",
                    "freeze_enabled": False,
                    "status": "OFF",
                    "reason": "Error budget within limits",
                    "created_at": result["last_updated"]
                }
                _write_json_atomic(freeze_file, freeze_data)
                print(f"Wrote: {freeze_file} (freeze cleared)")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Tower Error Budget Update")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    parser.add_argument("--write", action="store_true", help="Write output files")

    args = parser.parse_args()

    if args.write:
        result = update_error_budget()
    else:
        result = compute_error_budget()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Error Budget Status: {result['overall_status']}")
        for name, slo in result["slo_statuses"].items():
            value = slo["value"] if slo["value"] is not None else "N/A"
            print(f"  {name}: {value} ({slo['status']})")

        if result["freeze_triggered"]:
            print(f"\nFREEZE TRIGGERED: {', '.join(result['freeze_reasons'])}")

    return 1 if result["freeze_triggered"] else 0


if __name__ == "__main__":
    sys.exit(main())
