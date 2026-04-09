#!/usr/bin/env python3
"""
TruthCert HTA Lane Validator
Validates HTA outputs.

Per Spec v0.8 Section 14:
- Structural uncertainty required (or justification)
- Double counting defense
- Utility mapping validation
"""

import argparse
import json
from datetime import datetime
from pathlib import Path


def validate_hta(input_dir: Path, output_dir: Path) -> dict:
    """Validate HTA output."""

    issues = []
    p0_count = 0
    p1_count = 0
    p2_count = 0

    hta_output = input_dir / "hta_output.json"
    if not hta_output.exists():
        issues.append({
            "severity": "P0",
            "validator": "file_check",
            "message": "hta_output.json not found"
        })
        p0_count += 1
    else:
        with open(hta_output) as f:
            data = json.load(f)

        # Check model structure
        model = data.get("model_structure", {})
        if not model.get("type"):
            issues.append({
                "severity": "P0",
                "validator": "model_structure",
                "message": "model_structure type not defined"
            })
            p0_count += 1

        # Check structural uncertainty (Section 14.3)
        struct_unc = data.get("structural_uncertainty", {})
        if not struct_unc.get("included"):
            justification = struct_unc.get("justification_if_not")
            if not justification:
                issues.append({
                    "severity": "P0",
                    "validator": "structural_uncertainty",
                    "message": "Structural uncertainty not included and no justification provided"
                })
                p0_count += 1
            else:
                issues.append({
                    "severity": "P1",
                    "validator": "structural_uncertainty",
                    "message": f"Structural uncertainty excluded: {justification}"
                })
                p1_count += 1

        # Check double counting defense (Section 14.4)
        dc_check = data.get("double_counting_check", {})
        if dc_check.get("issues_found", 0) > 0:
            severity = dc_check.get("severity", "P1")
            issues.append({
                "severity": severity,
                "validator": "double_counting",
                "message": f"Double counting issues found: {dc_check['issues_found']}"
            })
            if severity == "P0":
                p0_count += 1
            else:
                p1_count += 1

        # Check utility mapping
        utility = data.get("utility_mapping", {})
        if not utility.get("instrument"):
            issues.append({
                "severity": "P0",
                "validator": "utility_mapping",
                "message": "Utility instrument not defined"
            })
            p0_count += 1

    result = {
        "spec_version": "0.8.0",
        "lane": "hta",
        "validator": "hta_validator",
        "validated_at": datetime.now().isoformat(),
        "overall_status": "PASS" if p0_count == 0 else "FAIL",
        "p0_count": p0_count,
        "p1_count": p1_count,
        "p2_count": p2_count,
        "issues": issues
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="TruthCert HTA Lane Validator")
    parser.add_argument("--input-dir", required=True, help="Input directory")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = validate_hta(input_dir, output_dir)

    output_file = output_dir / "validator_report.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Validation report: {output_file}")
    print(f"Status: {result['overall_status']}")

    if result["p0_count"] > 0:
        exit(1)


if __name__ == "__main__":
    main()
