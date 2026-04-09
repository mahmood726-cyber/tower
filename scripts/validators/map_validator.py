#!/usr/bin/env python3
"""
TruthCert Map Lane Validator
Validates map-level evidence graph.

Per Spec v0.8 Rule 2 (Guardianship):
- Validators never generate; they only recompute/check/veto.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path


def validate_map(input_dir: Path, output_dir: Path) -> dict:
    """Validate map output."""

    issues = []
    p0_count = 0
    p1_count = 0
    p2_count = 0

    # Check for required files
    map_output = input_dir / "map_output.json"
    if not map_output.exists():
        issues.append({
            "severity": "P0",
            "validator": "file_check",
            "message": "map_output.json not found"
        })
        p0_count += 1
    else:
        with open(map_output) as f:
            data = json.load(f)

        # Validate spec version
        if data.get("spec_version") != "0.8.0":
            issues.append({
                "severity": "P1",
                "validator": "version_check",
                "message": f"Unexpected spec_version: {data.get('spec_version')}"
            })
            p1_count += 1

        # Validate required fields
        required = ["lane", "topic", "generated_at"]
        for field in required:
            if field not in data:
                issues.append({
                    "severity": "P0",
                    "validator": "schema_check",
                    "message": f"Missing required field: {field}"
                })
                p0_count += 1

    result = {
        "spec_version": "0.8.0",
        "lane": "map",
        "validator": "map_validator",
        "validated_at": datetime.now().isoformat(),
        "overall_status": "PASS" if p0_count == 0 else "FAIL",
        "p0_count": p0_count,
        "p1_count": p1_count,
        "p2_count": p2_count,
        "issues": issues
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="TruthCert Map Lane Validator")
    parser.add_argument("--input-dir", required=True, help="Input directory")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = validate_map(input_dir, output_dir)

    output_file = output_dir / "validator_report.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Validation report: {output_file}")
    print(f"Status: {result['overall_status']}")
    print(f"P0: {result['p0_count']}, P1: {result['p1_count']}, P2: {result['p2_count']}")

    # Exit with non-zero if P0 issues found
    if result["p0_count"] > 0:
        exit(1)


if __name__ == "__main__":
    main()
