#!/usr/bin/env python3
"""
Tower Add-on Event Logger

Writes validated add-on events to a JSON file.
Validates against addon_event.schema.json if jsonschema is available.

Usage:
    python3 tower/scripts/addons/addon_event.py --event '<json>' --out <path>
    python3 tower/scripts/addons/addon_event.py --event-file <json_file> --out <path>
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

SPEC_VERSION = "v1.5.7"

# Try to import jsonschema
try:
    import jsonschema
    from jsonschema import Draft202012Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


def get_schema_path():
    """Get the path to the addon_event schema."""
    script_dir = Path(__file__).parent
    tower_root = script_dir.parent.parent
    return tower_root / "addons" / "qa" / "schemas" / "addon_event.schema.json"


def load_schema():
    """Load the addon_event schema if available."""
    schema_path = get_schema_path()
    if schema_path.exists():
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return None


def validate_event(event: dict, schema: dict) -> tuple:
    """Validate event against schema. Returns (is_valid, errors)."""
    if not HAS_JSONSCHEMA or not schema:
        return True, []

    try:
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(event))
        if errors:
            return False, [str(e.message) for e in errors]
        return True, []
    except Exception as e:
        return False, [str(e)]


def atomic_write_json(path: Path, data: dict):
    """Write JSON atomically using temp + rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix('.tmp')

    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())

    # Atomic rename
    if os.name == 'nt':  # Windows
        if path.exists():
            path.unlink()
    os.rename(tmp_path, path)


def create_event(event_type: str, addon: str, status: str,
                 card_id: str = None, run_id: str = None,
                 details: dict = None, pointers: list = None,
                 error_message: str = None) -> dict:
    """Create a new addon event with required fields."""
    event = {
        "spec_version": SPEC_VERSION,
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        "addon": addon,
        "status": status,
        "card_id": card_id,
        "run_id": run_id,
        "details": details or {},
        "pointers": pointers or [],
    }

    if error_message:
        event["error_message"] = error_message

    return event


def main():
    parser = argparse.ArgumentParser(description='Tower Add-on Event Logger')
    parser.add_argument('--event', type=str, help='Event as JSON string')
    parser.add_argument('--event-file', type=str, help='Path to JSON file with event')
    parser.add_argument('--out', type=str, required=True, help='Output path for event JSON')

    # Quick event creation
    parser.add_argument('--type', type=str, choices=[
        'PREFECT_RUN', 'MLFLOW_LOG', 'TRACE_LINK', 'ADDON_WARNING', 'ADDON_ERROR'
    ], help='Event type for quick creation')
    parser.add_argument('--addon', type=str, choices=['prefect', 'mlflow', 'tracing'],
                        help='Add-on name for quick creation')
    parser.add_argument('--status', type=str, choices=['OK', 'NOT_INSTALLED', 'FAILED', 'SKIPPED'],
                        help='Status for quick creation')
    parser.add_argument('--card', type=str, help='Card ID')
    parser.add_argument('--run-id', type=str, help='Run ID')
    parser.add_argument('--message', type=str, help='Error message if status is FAILED')

    args = parser.parse_args()

    # Determine event source
    event = None

    if args.event:
        try:
            event = json.loads(args.event)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in --event: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.event_file:
        try:
            with open(args.event_file, 'r', encoding='utf-8') as f:
                event = json.load(f)
        except Exception as e:
            print(f"ERROR: Could not read event file: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.type and args.addon and args.status:
        # Quick event creation
        event = create_event(
            event_type=args.type,
            addon=args.addon,
            status=args.status,
            card_id=args.card,
            run_id=args.run_id,
            error_message=args.message
        )

    else:
        print("ERROR: Provide --event, --event-file, or (--type, --addon, --status)", file=sys.stderr)
        sys.exit(1)

    # Load schema and validate
    schema = load_schema()

    if HAS_JSONSCHEMA and schema:
        is_valid, errors = validate_event(event, schema)
        if is_valid:
            event["schema_validation"] = "PASSED"
        else:
            print(f"WARNING: Schema validation failed: {errors}", file=sys.stderr)
            event["schema_validation"] = "FAILED"
            event.setdefault("details", {})["validation_errors"] = errors
    else:
        event["schema_validation"] = "SKIPPED"
        if not HAS_JSONSCHEMA:
            print("NOTE: jsonschema not installed, validation skipped", file=sys.stderr)

    # Write atomically
    out_path = Path(args.out)
    try:
        atomic_write_json(out_path, event)
        print(f"Event written: {out_path}")
    except Exception as e:
        print(f"ERROR: Could not write event: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
