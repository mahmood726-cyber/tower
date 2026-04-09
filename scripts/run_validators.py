#!/usr/bin/env python3
"""
Tower Validators Runner
Runs validators for a card and produces validator_report.json.

Usage:
    python3 run_validators.py --card CARD-XXX

Output:
    tower/artifacts/YYYY-MM-DD/CARD-XXX/validator_report.json

This is a STUB implementation. When real validators are added,
they should be registered and executed here.
"""

import sys
import os
import json
import argparse
from datetime import datetime
from pathlib import Path

SPEC_VERSION = "v1.5.7"

def get_tower_root():
    """Get the tower root directory."""
    script_dir = Path(__file__).parent
    return script_dir.parent

def generate_run_id():
    """Generate a unique run ID."""
    import random
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_part = hex(random.randint(0, 0xFFFF))[2:]
    return f"{timestamp}_{random_part}"

def run_validators(card_id: str) -> dict:
    """
    Run validators for a card.

    This is a stub that creates a schema-valid placeholder report.
    Real validators should be registered and executed here.
    """

    tower_root = get_tower_root()
    today = datetime.now().strftime("%Y-%m-%d")
    run_id = generate_run_id()

    # Create artifacts directory
    artifacts_dir = tower_root / "artifacts" / today / card_id / f"run_{run_id}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Define placeholder validators
    validators = [
        {
            "validator_id": "syntax_check",
            "name": "Syntax Check",
            "status": "NOT_RUN",
            "message": "Validator not implemented yet",
            "duration_seconds": None,
            "artifacts": [],
            "placeholder": True
        },
        {
            "validator_id": "type_check",
            "name": "Type Check",
            "status": "NOT_RUN",
            "message": "Validator not implemented yet",
            "duration_seconds": None,
            "artifacts": [],
            "placeholder": True
        },
        {
            "validator_id": "test_runner",
            "name": "Test Runner",
            "status": "NOT_RUN",
            "message": "Validator not implemented yet",
            "duration_seconds": None,
            "artifacts": [],
            "placeholder": True
        },
        {
            "validator_id": "lint_check",
            "name": "Lint Check",
            "status": "NOT_RUN",
            "message": "Validator not implemented yet",
            "duration_seconds": None,
            "artifacts": [],
            "placeholder": True
        }
    ]

    # Calculate summary
    total = len(validators)
    passed = sum(1 for v in validators if v["status"] == "PASS")
    failed = sum(1 for v in validators if v["status"] == "FAIL")
    not_run = sum(1 for v in validators if v["status"] == "NOT_RUN")

    # Determine overall status
    if failed > 0:
        overall_status = "FAIL"
    elif not_run == total:
        overall_status = "NOT_RUN"
    elif not_run > 0:
        overall_status = "PARTIAL"
    else:
        overall_status = "PASS"

    report = {
        "spec_version": SPEC_VERSION,
        "card_id": card_id,
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "overall_status": overall_status,
        "placeholder": True,
        "validators": validators,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "not_run": not_run
        }
    }

    # Write report atomically
    report_file = artifacts_dir / "validator_report.json"
    tmp_file = report_file.with_suffix(".json.tmp")

    with open(tmp_file, 'w') as f:
        json.dump(report, f, indent=2)

    tmp_file.replace(report_file)

    print(f"Validator report created: {report_file}")
    print(f"  Overall status: {overall_status}")
    print(f"  Passed: {passed}/{total}")
    print(f"  Failed: {failed}/{total}")
    print(f"  Not run: {not_run}/{total}")
    print()
    print("NOTE: This is a placeholder report. Real validators not implemented yet.")

    return report

def main():
    parser = argparse.ArgumentParser(description="Run validators for a Tower card")
    parser.add_argument("--card", required=True, help="Card ID (e.g., CARD-047)")
    args = parser.parse_args()

    card_id = args.card
    import re
    if not re.match(r'^CARD-\d+$', card_id):
        print(f"ERROR: Card ID must match CARD-NNN format, got: {card_id}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("Tower Validators Runner")
    print(f"Card: {card_id}")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)
    print()

    report = run_validators(card_id)

    # Exit based on overall status
    if report["overall_status"] == "FAIL":
        sys.exit(1)
    elif report["overall_status"] == "NOT_RUN":
        sys.exit(0)  # NOT_RUN is not a failure
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
