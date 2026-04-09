#!/usr/bin/env bash
#
# Tower PC Job Router
# Routes jobs to appropriate PCs based on requirements and availability.
#
# Usage:
#   pc_job_router.sh --job JOB_ID
#   pc_job_router.sh --analyze
#
# This is a STUB implementation.
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

MACHINES_FILE="$TOWER_ROOT/control/machines.json"
PC_SCORECARD="$TOWER_ROOT/control/pc_scorecard.json"

# Windows path versions for Python heredocs
TOWER_ROOT_WIN=$(to_win_path "$TOWER_ROOT")

# Parse arguments
JOB_ID=""
ANALYZE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --job)
            JOB_ID="$2"
            shift 2
            ;;
        --analyze)
            ANALYZE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "============================================================"
echo "Tower PC Job Router (STUB)"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"
echo ""
echo "NOTE: This is a placeholder implementation."
echo ""

export TOWER_ROOT_WIN="$TOWER_ROOT_WIN"
$PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
from pathlib import Path

tower_root = Path(os.environ.get('TOWER_ROOT_WIN', Path(__file__).parent.parent))

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

machines = load_json(tower_root / "control" / "machines.json")
scorecard = load_json(tower_root / "control" / "pc_scorecard.json")

print("Available PCs:")
print()

online_pcs = []
for machine_id, machine in machines.get("machines", {}).items():
    if machine.get("type") == "pc":
        is_online = machine.get("online", False)
        status = "ONLINE" if is_online else "OFFLINE"
        print(f"  {machine_id}: {status}")

        if is_online:
            online_pcs.append(machine_id)

print()

if not online_pcs:
    print("No online PCs available.")
    print("Routing recommendation: Use laptop or wait for PC availability")
else:
    # Simple routing logic (placeholder)
    recommended = online_pcs[0]  # Just pick first available
    print(f"Routing recommendation: {recommended}")
    print()
    print("Note: Real implementation would consider:")
    print("  - Current load on each PC")
    print("  - Job requirements (CPU, RAM, GPU)")
    print("  - Historical performance")
    print("  - Queue lengths")
PYTHON_SCRIPT

echo ""
echo "============================================================"
echo "Job routing analysis complete (placeholder)"
echo "============================================================"
