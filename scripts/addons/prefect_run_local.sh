#!/usr/bin/env bash
#
# Tower Prefect Local Runner
#
# Runs Prefect flows locally (no server required).
# If Prefect is not installed, writes addon_event and prints install instructions.
#
# Usage:
#   bash tower/scripts/addons/prefect_run_local.sh validate
#   bash tower/scripts/addons/prefect_run_local.sh daily
#   bash tower/scripts/addons/prefect_run_local.sh night
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
SPEC_VERSION="v1.5.7"

# Detect Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Neither python3 nor python found"
    exit 1
fi

# Convert path for Python
to_win_path() {
    local path="$1"
    if [[ "$path" == /[a-zA-Z]/* ]]; then
        echo "${path:1:1}:${path:2}"
    else
        echo "$path"
    fi
}

TOWER_ROOT_WIN=$(to_win_path "$TOWER_ROOT")

# Parse flow name
FLOW_NAME="${1:-validate}"

echo "============================================================"
echo "Tower Prefect Local Runner"
echo "Flow: $FLOW_NAME"
echo "Tower root: $TOWER_ROOT"
echo "============================================================"

# Check if Prefect is installed
PREFECT_INSTALLED=$($PYTHON_CMD -c "
try:
    import prefect
    print('yes')
except ImportError:
    print('no')
" 2>/dev/null || echo "no")

if [ "$PREFECT_INSTALLED" = "no" ]; then
    echo ""
    echo "Prefect is not installed."
    echo ""
    echo "To enable Prefect orchestration:"
    echo "  pip install prefect"
    echo ""
    echo "Prefect runs locally by default (no cloud account needed)."
    echo ""

    # Write addon event
    RECEIPTS_DIR="$TOWER_ROOT/addons/prefect/state/receipts"
    mkdir -p "$RECEIPTS_DIR"

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    $PYTHON_CMD "$SCRIPT_DIR/addon_event.py" \
        --type PREFECT_RUN \
        --addon prefect \
        --status NOT_INSTALLED \
        --message "pip install prefect to enable orchestration" \
        --out "$TOWER_ROOT_WIN/addons/prefect/state/receipts/not_installed_$TIMESTAMP.json"

    exit 0
fi

# Run the Prefect flow
echo ""
echo "Running Prefect flow: $FLOW_NAME"
echo ""

FLOW_SCRIPT="$TOWER_ROOT/addons/prefect/flows/tower_flow.py"
FLOW_SCRIPT_WIN=$(to_win_path "$FLOW_SCRIPT")

$PYTHON_CMD "$FLOW_SCRIPT_WIN" "$FLOW_NAME"
EXIT_CODE=$?

echo ""
echo "============================================================"
echo "Prefect flow complete"
echo "Exit code: $EXIT_CODE"
echo "============================================================"

exit $EXIT_CODE
