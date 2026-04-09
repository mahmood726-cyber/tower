#!/usr/bin/env python3
"""
Tower Control File Validator
Validates all known control files against their JSON schemas.

Usage:
    python3 validate_control_files.py [--strict]

Exit codes:
    0 - All validations passed (or files missing but not initialized)
    1 - Validation errors found
    2 - Schema loading error
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Try to import jsonschema, provide fallback if not available
try:
    import jsonschema
    from jsonschema import Draft202012Validator, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# Configuration
TOWER_ROOT = Path(__file__).parent.parent
CONTROL_DIR = TOWER_ROOT / "control"
SCHEMAS_DIR = TOWER_ROOT / "qa" / "schemas"
PAPERS_DIR = TOWER_ROOT / "papers"

# Mapping of control files to their schemas
FILE_SCHEMA_MAP = {
    "control/status.json": "status.schema.json",
    "control/quota.json": "quota.schema.json",
    "control/machines.json": "machines.schema.json",
    "control/model_scorecard.json": "model_scorecard.schema.json",
    "control/pc_scorecard.json": "pc_scorecard.schema.json",
    "control/costs.json": "costs.schema.json",
    "control/capacity_baseline.json": "capacity_baseline.schema.json",
    "control/drift_config.json": "drift_config.schema.json",
    "control/experiments.json": "experiment.schema.json",
    "control/backlog.json": "backlog.schema.json",
    "control/queues/night.json": "night_queue.schema.json",
    "control/queues/pc1_queue.json": "pc_queue.schema.json",
    "control/queues/pc2_queue.json": "pc_queue.schema.json",
    "control/queues/pc3_queue.json": "pc_queue.schema.json",
    "papers/paper_registry.json": "paper_registry.schema.json",
    "control/dashboard.json": "dashboard.schema.json",
    "control/dashboard_plus_status.json": "dashboard_plus_status.schema.json",
    "control/alerts/drift_alerts.json": "drift_alerts.schema.json",
    "control/alerts/efficiency_alerts.json": "efficiency_alerts.schema.json",
}


def load_json(path: Path) -> dict:
    """Load and parse a JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_with_jsonschema(data: dict, schema: dict, file_path: str) -> list:
    """Validate data against schema using jsonschema library."""
    errors = []
    validator = Draft202012Validator(schema)
    for error in validator.iter_errors(data):
        path = " -> ".join(str(p) for p in error.path) if error.path else "(root)"
        errors.append(f"  [{path}] {error.message}")
    return errors


def basic_validate(data, schema: dict, file_path: str) -> list:
    """
    Basic validation fallback when jsonschema is not available.
    Checks only top-level required fields and basic types.
    """
    errors = []

    # Check top-level type
    expected_top_type = schema.get("type")
    if expected_top_type == "array" and not isinstance(data, list):
        errors.append(f"  Expected top-level array, got {type(data).__name__}")
        return errors
    if expected_top_type == "array" and isinstance(data, list):
        return errors  # basic check passes for arrays

    if not isinstance(data, dict):
        errors.append(f"  Expected top-level object, got {type(data).__name__}")
        return errors

    # Check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in data:
            errors.append(f"  Missing required field: {field}")

    # Check basic types for present fields
    properties = schema.get("properties", {})
    for field, value in data.items():
        if field in properties:
            expected_type = properties[field].get("type")
            if expected_type:
                if isinstance(expected_type, list):
                    # Handle nullable types like ["string", "null"]
                    valid = False
                    for t in expected_type:
                        if t == "string" and isinstance(value, str):
                            valid = True
                        elif t == "integer" and isinstance(value, int) and not isinstance(value, bool):
                            valid = True
                        elif t == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
                            valid = True
                        elif t == "boolean" and isinstance(value, bool):
                            valid = True
                        elif t == "object" and isinstance(value, dict):
                            valid = True
                        elif t == "array" and isinstance(value, list):
                            valid = True
                        elif t == "null" and value is None:
                            valid = True
                    if not valid:
                        errors.append(f"  Field '{field}' has wrong type, expected one of {expected_type}")
                else:
                    type_map = {
                        "string": str,
                        "integer": int,
                        "number": (int, float),
                        "boolean": bool,
                        "object": dict,
                        "array": list,
                    }
                    expected = type_map.get(expected_type)
                    if expected:
                        # bool is subclass of int in Python; exclude for integer/number
                        if expected_type in ("integer", "number") and isinstance(value, bool):
                            errors.append(f"  Field '{field}' has wrong type, expected {expected_type}")
                        elif not isinstance(value, expected):
                            errors.append(f"  Field '{field}' has wrong type, expected {expected_type}")

    return errors


def validate_file(file_rel_path: str, schema_name: str, strict: bool = False) -> tuple:
    """
    Validate a single file against its schema.

    Returns:
        (status, messages) where status is 'PASS', 'FAIL', 'MISSING', or 'SKIP'
    """
    file_path = TOWER_ROOT / file_rel_path
    schema_path = SCHEMAS_DIR / schema_name

    # Check if file exists
    if not file_path.exists():
        return ("MISSING", [f"File not found (ok if not initialized yet)"])

    # Check if schema exists
    if not schema_path.exists():
        return ("SKIP", [f"Schema not found: {schema_name}"])

    # Load files
    try:
        data = load_json(file_path)
    except json.JSONDecodeError as e:
        return ("FAIL", [f"Invalid JSON: {e}"])
    except Exception as e:
        return ("FAIL", [f"Error reading file: {e}"])

    try:
        schema = load_json(schema_path)
    except Exception as e:
        return ("FAIL", [f"Error reading schema: {e}"])

    # Validate
    if HAS_JSONSCHEMA:
        errors = validate_with_jsonschema(data, schema, str(file_path))
    else:
        errors = basic_validate(data, schema, str(file_path))

    if errors:
        return ("FAIL", errors)

    return ("PASS", [])


def main():
    strict = "--strict" in sys.argv

    print("=" * 60)
    print("Tower Control File Validator")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Tower root: {TOWER_ROOT}")
    print(f"jsonschema available: {HAS_JSONSCHEMA}")
    if not HAS_JSONSCHEMA:
        print("  (Install with: pip install jsonschema)")
        print("  Using basic fallback validation")
    print("=" * 60)
    print()

    results = {
        "PASS": [],
        "FAIL": [],
        "MISSING": [],
        "SKIP": [],
    }

    for file_rel_path, schema_name in FILE_SCHEMA_MAP.items():
        status, messages = validate_file(file_rel_path, schema_name, strict)
        results[status].append((file_rel_path, messages))

        icon = {"PASS": "+", "FAIL": "X", "MISSING": "?", "SKIP": "-"}.get(status, "?")
        print(f"[{icon}] {file_rel_path}")
        for msg in messages:
            print(f"    {msg}")

    print()
    print("-" * 60)
    print("Summary:")
    print(f"  PASS:    {len(results['PASS'])}")
    print(f"  FAIL:    {len(results['FAIL'])}")
    print(f"  MISSING: {len(results['MISSING'])}")
    print(f"  SKIP:    {len(results['SKIP'])}")
    print("-" * 60)

    if results["FAIL"]:
        print("\nVALIDATION FAILED")
        return 1

    print("\nVALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
