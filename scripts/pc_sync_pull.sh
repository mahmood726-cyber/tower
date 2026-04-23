#!/usr/bin/env bash
#
# Tower PC Sync Pull
# Pulls artifacts from remote PCs to local tower.
#
# Usage:
#   pc_sync_pull.sh --pc PC_ID [--date YYYY-MM-DD]
#
# This is a STUB implementation.
# In production, this would use rsync or similar.
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
        # Convert /<drive>/Users/... to <drive>:/Users/... (keep forward slashes for Python)
        echo "${path:1:1}:${path:2}"
    else
        echo "$path"
    fi
}

# Parse arguments
PC_ID=""
SYNC_DATE=$(date +%Y-%m-%d)

while [[ $# -gt 0 ]]; do
    case $1 in
        --pc)
            PC_ID="$2"
            shift 2
            ;;
        --date)
            SYNC_DATE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$PC_ID" ]; then
    echo "ERROR: --pc is required"
    echo "Usage: pc_sync_pull.sh --pc PC_ID [--date YYYY-MM-DD]"
    exit 1
fi

echo "============================================================"
echo "Tower PC Sync Pull (STUB)"
echo "PC: $PC_ID"
echo "Date: $SYNC_DATE"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"
echo ""
echo "NOTE: This is a placeholder implementation."
echo "      rsync is not configured."
echo ""

# Check if PC is configured
MACHINES_FILE="$TOWER_ROOT/control/machines.json"
MACHINES_FILE_WIN=$(to_win_path "$MACHINES_FILE")
if [ -f "$MACHINES_FILE" ]; then
    PC_INFO=$($PYTHON_CMD -c "
import json
with open('$MACHINES_FILE_WIN') as f:
    data = json.load(f)
pc = data.get('machines', {}).get('$PC_ID', {})
print(f\"Online: {pc.get('online', False)}\")
print(f\"Hostname: {pc.get('hostname', 'Not configured')}\")
" 2>/dev/null || echo "PC not found")

    echo "PC Configuration:"
    echo "$PC_INFO"
    echo ""
fi

echo "Would sync:"
echo "  Remote: $PC_ID:/path/to/tower/artifacts/$SYNC_DATE/"
echo "  Local:  $TOWER_ROOT/artifacts/$SYNC_DATE/"
echo ""
echo "To implement:"
echo "  1. Configure PC hostnames in machines.json"
echo "  2. Set up SSH key authentication"
echo "  3. Use: rsync -avz user@\$PC_HOST:/tower/artifacts/ $TOWER_ROOT/artifacts/"
echo ""

# Update pc_scorecard with sync attempt
TOWER_ROOT_WIN=$(to_win_path "$TOWER_ROOT")
export TOWER_ROOT_WIN="$TOWER_ROOT_WIN"
export PC_ID="$PC_ID"
$PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
from datetime import datetime
from pathlib import Path

tower_root = Path(os.environ.get('TOWER_ROOT_WIN', Path(__file__).parent.parent))
pc_id = os.environ.get('PC_ID', '')

scorecard_file = tower_root / "control" / "pc_scorecard.json"

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

scorecard = load_json(scorecard_file)
if "pcs" not in scorecard:
    scorecard = {"spec_version": "v1.5.5", "pcs": {}}

if pc_id not in scorecard["pcs"]:
    scorecard["pcs"][pc_id] = {"pc_id": pc_id}

scorecard["pcs"][pc_id]["last_sync_attempt"] = datetime.now().isoformat()
scorecard["pcs"][pc_id]["placeholder"] = True
scorecard["last_updated"] = datetime.now().isoformat()

tmp_file = str(scorecard_file) + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(scorecard, f, indent=2)
os.replace(tmp_file, str(scorecard_file))

print(f"Sync attempt recorded in pc_scorecard.json")
PYTHON_SCRIPT

echo ""
echo "============================================================"
echo "Sync pull stub complete"
echo "============================================================"
