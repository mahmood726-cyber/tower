#!/usr/bin/env python3
"""
TruthCert Transport Lane Validator
Validates transportability outputs.

Per Spec v0.8 Section 13.2:
- Default overlap metric validation
- Baseline risk shift checks
"""

import argparse
import json
from datetime import datetime
from pathlib import Path


def validate_transport(input_dir: Path, output_dir: Path) -> dict:
    """Validate transport output."""

    issues = []
    p0_count = 0
    p1_count = 0
    p2_count = 0

    transport_output = input_dir / "transport_output.json"
    if not transport_output.exists():
        issues.append({
            "severity": "P0",
            "validator": "file_check",
            "message": "transport_output.json not found"
        })
        p0_count += 1
    else:
        with open(transport_output) as f:
            data = json.load(f)

        # Check target population schema
        schema = data.get("target_population_schema", {})
        if not schema.get("covariates"):
            issues.append({
                "severity": "P1",
                "validator": "schema_check",
                "message": "No covariates defined in target_population_schema"
            })
            p1_count += 1

        # Check overlap metric
        overlap = data.get("overlap_metric", {})
        if overlap.get("value") is not None:
            threshold = overlap.get("threshold", 0.1)
            if overlap["value"] < threshold:
                issues.append({
                    "severity": "P1",
                    "validator": "overlap_check",
                    "message": f"Overlap {overlap['value']} below threshold {threshold}"
                })
                p1_count += 1

        # Check baseline risk policy
        if not data.get("baseline_risk_policy", {}).get("source"):
            issues.append({
                "severity": "P0",
                "validator": "baseline_risk",
                "message": "baseline_risk_policy source not defined"
            })
            p0_count += 1

    result = {
        "spec_version": "0.8.0",
        "lane": "transport",
        "validator": "transport_validator",
        "validated_at": datetime.now().isoformat(),
        "overall_status": "PASS" if p0_count == 0 else "FAIL",
        "p0_count": p0_count,
        "p1_count": p1_count,
        "p2_count": p2_count,
        "issues": issues
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="TruthCert Transport Lane Validator")
    parser.add_argument("--input-dir", required=True, help="Input directory")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = validate_transport(input_dir, output_dir)

    output_file = output_dir / "validator_report.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Validation report: {output_file}")
    print(f"Status: {result['overall_status']}")

    if result["p0_count"] > 0:
        exit(1)


if __name__ == "__main__":
    main()
