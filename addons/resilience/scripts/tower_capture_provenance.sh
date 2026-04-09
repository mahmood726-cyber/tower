#!/usr/bin/env bash
#
# Capture environment provenance (no secrets)
#
# Usage:
#   bash tower/addons/resilience/scripts/tower_capture_provenance.sh --out provenance.json
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"

usage() {
    echo "Usage: $0 --out <output_file> [--machine-id <id>]"
    exit 1
}

OUTPUT_FILE=""
MACHINE_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --out)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --machine-id)
            MACHINE_ID="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if [[ -z "$OUTPUT_FILE" ]]; then
    echo "ERROR: --out is required"
    usage
fi

# Gather provenance data
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
HOSTNAME_VAL=$(hostname 2>/dev/null || echo "unknown")
UNAME_VAL=$(uname -a 2>/dev/null || echo "unknown")

# Git info
GIT_SHA=""
GIT_STATUS=""
if command -v git &> /dev/null; then
    GIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "")
    GIT_STATUS=$(git status --porcelain 2>/dev/null | head -20 || echo "")
fi

# Python version
PYTHON_VERSION=""
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 || echo "")
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1 || echo "")
fi

# Spec version from any control file
SPEC_VERSION=""
if [[ -f "$TOWER_ROOT/control/status.json" ]]; then
    if command -v jq &> /dev/null; then
        SPEC_VERSION=$(jq -r '.spec_version // ""' "$TOWER_ROOT/control/status.json" 2>/dev/null || echo "")
    else
        SPEC_VERSION=$(grep -o '"spec_version"[[:space:]]*:[[:space:]]*"[^"]*"' "$TOWER_ROOT/control/status.json" 2>/dev/null | cut -d'"' -f4 || echo "")
    fi
fi

# Pip freeze (if venv exists)
PIP_FREEZE=""
if [[ -d "$TOWER_ROOT/.venv_addons" ]]; then
    if [[ -f "$TOWER_ROOT/.venv_addons/bin/pip" ]]; then
        PIP_FREEZE=$("$TOWER_ROOT/.venv_addons/bin/pip" freeze 2>/dev/null | head -50 || echo "")
    fi
fi

# Machine ID
if [[ -z "$MACHINE_ID" ]]; then
    MACHINE_ID="$HOSTNAME_VAL"
fi

# Build JSON
# Using Python for proper JSON escaping
python3 - "$OUTPUT_FILE" "$TIMESTAMP" "$HOSTNAME_VAL" "$UNAME_VAL" "$GIT_SHA" "$GIT_STATUS" "$PYTHON_VERSION" "$SPEC_VERSION" "$PIP_FREEZE" "$MACHINE_ID" << 'PYTHON_SCRIPT'
import json
import sys
import os

output_file = sys.argv[1]
timestamp = sys.argv[2]
hostname = sys.argv[3]
uname = sys.argv[4]
git_sha = sys.argv[5]
git_status = sys.argv[6]
python_version = sys.argv[7]
spec_version = sys.argv[8]
pip_freeze = sys.argv[9]
machine_id = sys.argv[10]

provenance = {
    "spec_version": spec_version or "v1.5.5",
    "timestamp": timestamp,
    "machine_id": machine_id,
    "hostname": hostname,
    "uname": uname,
    "git_sha": git_sha or None,
    "git_status_porcelain": git_status[:1000] if git_status else None,
    "python_version": python_version or None,
    "pip_freeze": pip_freeze[:2000] if pip_freeze else None
}

# Atomic write
tmp_file = output_file + ".tmp"
with open(tmp_file, "w") as f:
    json.dump(provenance, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
os.replace(tmp_file, output_file)

print(f"Wrote: {output_file}")
PYTHON_SCRIPT
