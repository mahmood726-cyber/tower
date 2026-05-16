#!/usr/bin/env bash
#
# Tower PC Health Check
# Checks health of PC fleet and updates pc_scorecard.json
#
# Usage:
#   pc_health_check.sh [--pc PC_ID]
#
# This is a STUB implementation.
# Writes schema-valid placeholders to pc_scorecard.json.
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

PC_SCORECARD="$TOWER_ROOT/control/pc_scorecard.json"
MACHINES_FILE="$TOWER_ROOT/control/machines.json"

# Windows path versions for Python heredocs
TOWER_ROOT_WIN=$(to_win_path "$TOWER_ROOT")

# Parse arguments
TARGET_PC=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --pc)
            TARGET_PC="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "============================================================"
echo "Tower PC Health Check (STUB)"
echo "Target: ${TARGET_PC:-all PCs}"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"
echo ""
echo "NOTE: This is a placeholder implementation."
echo "      Real CPU/RAM metrics are not collected."
echo ""

export TOWER_ROOT_WIN="$TOWER_ROOT_WIN"
export TARGET_PC="$TARGET_PC"
$PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
from datetime import datetime
from pathlib import Path

tower_root = Path(os.environ.get('TOWER_ROOT_WIN', Path(__file__).parent.parent))
spec_version = "v1.5.5"
target_pc = os.environ.get('TARGET_PC', '')

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

scorecard_file = tower_root / "control" / "pc_scorecard.json"
machines_file = tower_root / "control" / "machines.json"

scorecard = load_json(scorecard_file)
machines = load_json(machines_file)

if "pcs" not in scorecard:
    scorecard = {
        "spec_version": spec_version,
        "last_updated": datetime.now().isoformat(),
        "pcs": {}
    }

# Get PCs to check
pcs_to_check = []
if target_pc:
    pcs_to_check = [target_pc]
else:
    for machine_id, machine in machines.get("machines", {}).items():
        if machine.get("type") == "pc":
            pcs_to_check.append(machine_id)

print(f"Checking {len(pcs_to_check)} PCs...")
print()

for pc_id in pcs_to_check:
    print(f"PC: {pc_id}")

    # Check if PC is in machines.json
    machine = machines.get("machines", {}).get(pc_id, {})
    is_online = machine.get("online", False)

    # Update scorecard with placeholder values
    if pc_id not in scorecard["pcs"]:
        scorecard["pcs"][pc_id] = {"pc_id": pc_id}

    pc = scorecard["pcs"][pc_id]
    pc["online"] = is_online
    pc["last_health_check"] = datetime.now().isoformat()
    pc["placeholder"] = True

    # Placeholder metrics
    pc["avg_cpu_utilization"] = None  # Would need real implementation
    pc["avg_ram_utilization"] = None

    print(f"  Online: {is_online}")
    print(f"  CPU: placeholder (not implemented)")
    print(f"  RAM: placeholder (not implemented)")
    print()

scorecard["last_updated"] = datetime.now().isoformat()
scorecard["spec_version"] = spec_version

# Atomic write
tmp_file = str(scorecard_file) + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(scorecard, f, indent=2)
os.replace(tmp_file, str(scorecard_file))

print(f"Scorecard updated: {scorecard_file}")
PYTHON_SCRIPT

echo ""
echo "============================================================"
echo "PC health check complete (placeholder data)"
echo "============================================================"
