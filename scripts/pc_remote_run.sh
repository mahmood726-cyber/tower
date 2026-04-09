#!/usr/bin/env bash
#
# Tower PC Remote Run
# Executes a command on a remote PC.
#
# Usage:
#   pc_remote_run.sh --pc PC_ID --cmd "<command>"
#
# This is a STUB implementation.
# In production, this would use SSH or similar to execute remotely.
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

# Parse arguments
PC_ID=""
CMD=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --pc)
            PC_ID="$2"
            shift 2
            ;;
        --cmd)
            CMD="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$PC_ID" ] || [ -z "$CMD" ]; then
    echo "ERROR: --pc and --cmd are required"
    echo "Usage: pc_remote_run.sh --pc PC_ID --cmd \"<command>\""
    exit 1
fi

# Validate PC_ID format (alphanumeric, underscores, dashes only - prevent injection)
if ! echo "$PC_ID" | grep -qE '^[a-zA-Z0-9_-]+$'; then
    echo "ERROR: --pc must be alphanumeric with underscores/dashes only (got: $PC_ID)"
    exit 1
fi

echo "============================================================"
echo "Tower PC Remote Run (STUB)"
echo "PC: $PC_ID"
echo "Command: $CMD"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"
echo ""
echo "NOTE: This is a placeholder implementation."
echo "      Remote execution is not implemented."
echo ""

# Check if PC is online
MACHINES_FILE="$TOWER_ROOT/control/machines.json"
MACHINES_FILE_WIN=$(to_win_path "$MACHINES_FILE")
if [ -f "$MACHINES_FILE" ]; then
    IS_ONLINE=$(_PC_MACHINES="$MACHINES_FILE_WIN" _PC_ID="$PC_ID" $PYTHON_CMD << 'PYEOF'
import json, os
machines_file = os.environ.get('_PC_MACHINES', '')
pc_id = os.environ.get('_PC_ID', '')
try:
    with open(machines_file) as f:
        data = json.load(f)
    pc = data.get('machines', {}).get(pc_id, {})
    print('true' if pc.get('online') else 'false')
except:
    print('false')
PYEOF
)

    if [ "$IS_ONLINE" = "false" ]; then
        echo "ERROR: PC $PC_ID is not online"
        exit 1
    fi
fi

echo "Would execute on $PC_ID:"
echo "  $CMD"
echo ""
echo "To implement:"
echo "  1. Configure SSH access to PCs"
echo "  2. Set up host keys in machines.json"
echo "  3. Use: ssh user@\$PC_HOST \"\$CMD\""
echo ""

# Create a placeholder run context
TODAY=$(date +%Y-%m-%d)
RUN_ID="$(date +%Y%m%d_%H%M%S)_stub"
ARTIFACTS_DIR="$TOWER_ROOT/artifacts/$TODAY/PC_$PC_ID/run_$RUN_ID"
mkdir -p "$ARTIFACTS_DIR"

cat > "$ARTIFACTS_DIR/run_context.json" << EOF
{
  "run_id": "$RUN_ID",
  "card_id": "PC-$PC_ID",
  "session": null,
  "model": null,
  "command": $(echo "$CMD" | $PYTHON_CMD -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))'),
  "start_time": "$(date -Iseconds)",
  "working_dir": null,
  "git_sha": null,
  "git_branch": null,
  "spec_version": "$SPEC_VERSION",
  "machine": "$PC_ID",
  "environment": {},
  "placeholder": true
}
EOF

cat > "$ARTIFACTS_DIR/run_summary.json" << EOF
{
  "run_id": "$RUN_ID",
  "card_id": "PC-$PC_ID",
  "exit_code": -1,
  "start_time": "$(date -Iseconds)",
  "end_time": "$(date -Iseconds)",
  "duration_seconds": 0,
  "spec_version": "$SPEC_VERSION",
  "placeholder": true,
  "message": "Remote execution not implemented"
}
EOF

echo "Placeholder artifacts created: $ARTIFACTS_DIR"
echo ""
echo "============================================================"
echo "Remote run stub complete"
echo "============================================================"
