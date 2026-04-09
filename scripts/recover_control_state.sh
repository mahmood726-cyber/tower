#!/usr/bin/env bash
#
# Tower Control State Recovery
# Recovers status.json from backup or rebuilds from artifacts.
#
# Usage:
#   recover_control_state.sh [--force-rebuild]
#
# Operations:
#   1. Validates current status.json
#   2. If invalid, restores from latest valid backup
#   3. If no valid backup, rebuilds from artifacts directory
#   4. Creates incident record
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$SCRIPT_DIR")"

# Detect Python command (python3 or python)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Neither python3 nor python found"
    exit 1
fi

SPEC_VERSION="v1.5.7"

# Convert Git Bash path to Windows path for Python (using forward slashes)
to_win_path() {
    local path="$1"
    if [[ "$path" == /[a-zA-Z]/* ]]; then
        # Convert /c/Users/... to C:/Users/... (keep forward slashes for Python)
        echo "${path:1:1}:${path:2}"
    else
        echo "$path"
    fi
}

STATUS_FILE="$TOWER_ROOT/control/status.json"
BACKUP_DIR="$TOWER_ROOT/control/backups"
INCIDENTS_DIR="$TOWER_ROOT/control/incidents"

# Windows path versions for Python heredocs
TOWER_ROOT_WIN=$(to_win_path "$TOWER_ROOT")

# Parse arguments
FORCE_REBUILD=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --force-rebuild)
            FORCE_REBUILD=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Ensure directories exist
mkdir -p "$BACKUP_DIR" "$INCIDENTS_DIR"

echo "============================================================"
echo "Tower Control State Recovery"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"

# Validate JSON file
validate_json() {
    local file="$1"
    local file_win=$(to_win_path "$file")
    if [ ! -f "$file" ]; then
        return 1
    fi

    if command -v jq &> /dev/null; then
        jq empty "$file" 2>/dev/null
        return $?
    else
        $PYTHON_CMD -c "import json; json.load(open('$file_win'))" 2>/dev/null
        return $?
    fi
}

# Create incident record
create_incident() {
    local incident_type="$1"
    local description="$2"
    local resolution="$3"

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local incident_id="INC_${timestamp}"
    local incident_file="$INCIDENTS_DIR/${timestamp}_status_rebuild.json"
    local incident_md="$INCIDENTS_DIR/${timestamp}_status_rebuild.md"

    # JSON incident
    cat > "$incident_file" << EOF
{
  "spec_version": "$SPEC_VERSION",
  "incident_id": "$incident_id",
  "type": "$incident_type",
  "severity": "medium",
  "description": "$description",
  "status": "resolved",
  "created_at": "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)",
  "resolved_at": "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)",
  "related_cards": [],
  "artifacts": [],
  "resolution": "$resolution",
  "root_cause": "Unknown - requires investigation",
  "preventive_action": "Enable regular validation checks"
}
EOF

    # Markdown incident
    cat > "$incident_md" << EOF
# Incident: $incident_id

**Type:** $incident_type
**Severity:** Medium
**Created:** $(date -Iseconds 2>/dev/null || date)
**Status:** Resolved

## Description

$description

## Resolution

$resolution

## Root Cause

Unknown - requires investigation.

## Preventive Action

- Enable regular validation checks
- Monitor drift alerts
- Review backup procedures
EOF

    echo "Incident created: $incident_file"
}

# Rebuild status from artifacts
rebuild_from_artifacts() {
    echo "Rebuilding status.json from artifacts..."

    export TOWER_ROOT_WIN="$TOWER_ROOT_WIN"
    $PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
from datetime import datetime
from pathlib import Path

tower_root = os.environ.get('TOWER_ROOT_WIN', Path(__file__).parent.parent)
if isinstance(tower_root, str):
    tower_root = Path(tower_root)

artifacts_dir = tower_root / "artifacts"
status_file = tower_root / "control" / "status.json"

cards = {}

# Scan artifacts directory for cards
if artifacts_dir.exists():
    for date_dir in artifacts_dir.iterdir():
        if date_dir.is_dir() and date_dir.name.startswith("20"):
            for card_dir in date_dir.iterdir():
                if card_dir.is_dir() and card_dir.name.startswith("CARD-"):
                    card_id = card_dir.name

                    if card_id not in cards:
                        cards[card_id] = {
                            "card_id": card_id,
                            "state": "ACTIVE",
                            "stream": "apps",
                            "window": None,
                            "gates": {
                                "tests": "NOT_RUN",
                                "validators": "NOT_RUN",
                                "proofpack": "NOT_RUN"
                            },
                            "color": "YELLOW",
                            "updated_at": datetime.now().isoformat(),
                            "run_ids": []
                        }

                    # Collect run_ids
                    for run_dir in card_dir.iterdir():
                        if run_dir.is_dir() and run_dir.name.startswith("run_"):
                            run_id = run_dir.name.replace("run_", "")
                            if run_id not in cards[card_id]["run_ids"]:
                                cards[card_id]["run_ids"].append(run_id)

status = {
    "spec_version": "v1.5.5",
    "last_updated": datetime.now().isoformat(),
    "cards": cards
}

# Atomic write
tmp_file = str(status_file) + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(status, f, indent=2)

os.replace(tmp_file, str(status_file))
print(f"Rebuilt status with {len(cards)} cards")
PYTHON_SCRIPT
}

# Restore from backup
restore_from_backup() {
    echo "Looking for valid backups..."

    # Find most recent valid backup
    local latest_valid=""
    for backup in $(ls -t "$BACKUP_DIR"/status_*.json 2>/dev/null); do
        if validate_json "$backup"; then
            latest_valid="$backup"
            break
        fi
    done

    if [ -n "$latest_valid" ]; then
        echo "Found valid backup: $latest_valid"
        cp "$latest_valid" "$STATUS_FILE"
        return 0
    else
        echo "No valid backup found"
        return 1
    fi
}

# Main recovery logic
echo ""

# Check if force rebuild requested
if [ "$FORCE_REBUILD" = true ]; then
    echo "Force rebuild requested..."
    rebuild_from_artifacts
    create_incident "corruption" "Forced rebuild of status.json requested" "Rebuilt from artifacts directory"
    echo ""
    echo "Recovery complete (forced rebuild)."
    exit 0
fi

# Check current status.json
echo "Validating current status.json..."
if validate_json "$STATUS_FILE"; then
    echo "  status.json is valid. No recovery needed."
    exit 0
fi

echo "  status.json is INVALID or missing."
echo ""

# Try to restore from backup
echo "Attempting restore from backup..."
if restore_from_backup; then
    create_incident "corruption" "status.json was invalid/corrupted" "Restored from backup"
    echo ""
    echo "Recovery complete (restored from backup)."
    exit 0
fi

# Rebuild from artifacts
echo ""
echo "No valid backup found. Rebuilding from artifacts..."
rebuild_from_artifacts
create_incident "corruption" "status.json was invalid and no valid backup found" "Rebuilt from artifacts directory structure"

echo ""
echo "============================================================"
echo "Recovery complete (rebuilt from artifacts)."
echo "============================================================"
