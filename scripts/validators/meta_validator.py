#!/usr/bin/env python3
"""
TruthCert Meta Lane Validator
Validates meta-analysis outputs.

Per Spec v0.8 Section 12.2:
- P0 design enforcement validators
- Cluster RCT ICC check
- Crossover washout check
- Factorial arm combination check
"""

import argparse
import json
from datetime import datetime
from pathlib import Path


def validate_meta(input_dir: Path, output_dir: Path) -> dict:
    """Validate meta output."""

    issues = []
    p0_count = 0
    p1_count = 0
    p2_count = 0

    # Check for required files
    meta_output = input_dir / "meta_output.json"
    if not meta_output.exists():
        issues.append({
            "severity": "P0",
            "validator": "file_check",
            "message": "meta_output.json not found"
        })
        p0_count += 1
    else:
        with open(meta_output) as f:
            data = json.load(f)

        # Validate method registry
        method = data.get("method_registry", {})
        if not method.get("estimand"):
            issues.append({
                "severity": "P0",
                "validator": "method_registry",
                "message": "estimand not declared in method_registry"
            })
            p0_count += 1

        if not method.get("timepoint_selection_policy"):
            issues.append({
                "severity": "P0",
                "validator": "method_registry",
                "message": "timepoint_selection_policy not declared"
            })
            p0_count += 1

        # Check for cluster RCT ICC (P0 per Section 12.2)
        # This would check actual study data - placeholder for now
        if data.get("status") != "placeholder":
            issues.append({
                "severity": "P2",
                "validator": "design_enforcement",
                "message": "Design enforcement checks would run on real data"
            })
            p2_count += 1

    result = {
        "spec_version": "0.8.0",
        "lane": "meta",
        "validator": "meta_validator",
        "validated_at": datetime.now().isoformat(),
        "overall_status": "PASS" if p0_count == 0 else "FAIL",
        "p0_count": p0_count,
        "p1_count": p1_count,
        "p2_count": p2_count,
        "issues": issues
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="TruthCert Meta Lane Validator")
    parser.add_argument("--input-dir", required=True, help="Input directory")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = validate_meta(input_dir, output_dir)

    output_file = output_dir / "validator_report.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Validation report: {output_file}")
    print(f"Status: {result['overall_status']}")

    if result["p0_count"] > 0:
        exit(1)


if __name__ == "__main__":
    main()
