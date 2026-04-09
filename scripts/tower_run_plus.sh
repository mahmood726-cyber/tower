#!/usr/bin/env bash
#
# Tower Run Plus - Enhanced wrapper with add-on support
#
# Wraps tower_run.sh with optional MLflow logging and LangSmith tracing.
# Does NOT modify tower_run.sh behavior - purely additive.
#
# Usage:
#   tower_run_plus.sh --card CARD-XXX --session apps_dev1 --model claude_opus \
#       --cmd "<command>" [--enable-mlflow] [--enable-tracing]
#
# Creates:
#   - All normal tower_run.sh artifacts
#   - <run_dir>/addon_receipt.json (orchestrator_run.schema.json)
#   - <run_dir>/addon_mlflow_event.json (if mlflow enabled)
#   - <run_dir>/addon_trace_event.json (if tracing enabled)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$SCRIPT_DIR")"
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

# Convert Git Bash path to Windows path for Python
to_win_path() {
    local path="$1"
    if [[ "$path" == /[a-zA-Z]/* ]]; then
        echo "${path:1:1}:${path:2}"
    else
        echo "$path"
    fi
}

# Parse arguments
CARD_ID=""
SESSION=""
MODEL=""
CMD=""
ENABLE_MLFLOW=false
ENABLE_TRACING=false

# Collect args for tower_run.sh
TOWER_RUN_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --card)
            CARD_ID="$2"
            TOWER_RUN_ARGS+=("--card" "$2")
            shift 2
            ;;
        --session)
            SESSION="$2"
            TOWER_RUN_ARGS+=("--session" "$2")
            shift 2
            ;;
        --model)
            MODEL="$2"
            TOWER_RUN_ARGS+=("--model" "$2")
            shift 2
            ;;
        --cmd)
            CMD="$2"
            TOWER_RUN_ARGS+=("--cmd" "$2")
            shift 2
            ;;
        --enable-mlflow)
            ENABLE_MLFLOW=true
            shift
            ;;
        --enable-tracing)
            ENABLE_TRACING=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$CARD_ID" ]; then
    echo "ERROR: --card is required"
    echo "Usage: tower_run_plus.sh --card CARD-XXX --session apps_dev1 --model claude_opus --cmd \"<cmd>\" [--enable-mlflow] [--enable-tracing]"
    exit 1
fi

if [ -z "$CMD" ]; then
    echo "ERROR: --cmd is required"
    exit 1
fi

echo "============================================================"
echo "Tower Run Plus (with add-on support)"
echo "Card: $CARD_ID"
echo "Session: ${SESSION:-N/A}"
echo "Model: ${MODEL:-N/A}"
echo "MLflow: $([ "$ENABLE_MLFLOW" = true ] && echo 'enabled' || echo 'disabled')"
echo "Tracing: $([ "$ENABLE_TRACING" = true ] && echo 'enabled' || echo 'disabled')"
echo "============================================================"
echo ""

# Run tower_run.sh and capture output
TOWER_RUN_OUTPUT=$(bash "$SCRIPT_DIR/tower_run.sh" "${TOWER_RUN_ARGS[@]}" 2>&1)
TOWER_EXIT_CODE=$?

echo "$TOWER_RUN_OUTPUT"

# Find the run directory from output
DATE_DIR=$(date +%Y-%m-%d)
ARTIFACTS_BASE="$TOWER_ROOT/artifacts/$DATE_DIR/$CARD_ID"

# Find the latest run directory
RUN_DIR=""
if [ -d "$ARTIFACTS_BASE" ]; then
    RUN_DIR=$(ls -td "$ARTIFACTS_BASE"/run_* 2>/dev/null | head -1)
fi

if [ -z "$RUN_DIR" ]; then
    echo ""
    echo "WARNING: Could not find run directory. Add-ons skipped."
    exit $TOWER_EXIT_CODE
fi

RUN_ID=$(basename "$RUN_DIR" | sed 's/run_//')
RUN_DIR_WIN=$(to_win_path "$RUN_DIR")

echo ""
echo "------------------------------------------------------------"
echo "Running add-ons..."
echo "Run directory: $RUN_DIR"
echo "------------------------------------------------------------"

# Initialize addon results
MLFLOW_STATUS="DISABLED"
MLFLOW_RUN_ID=""
TRACING_STATUS="DISABLED"
TRACE_URL=""

# Run MLflow logging if enabled
if [ "$ENABLE_MLFLOW" = true ]; then
    echo ""
    echo "MLflow logging..."
    MLFLOW_OUTPUT=$($PYTHON_CMD "$SCRIPT_DIR/addons/mlflow_log_run.py" \
        --card "$CARD_ID" \
        --run_dir "$RUN_DIR_WIN" \
        --spec_version "$SPEC_VERSION" 2>&1) || true
    echo "$MLFLOW_OUTPUT"

    # Parse status from addon event
    if [ -f "$RUN_DIR/addon_mlflow_event.json" ]; then
        MLFLOW_STATUS=$($PYTHON_CMD -c "import json; print(json.load(open('$RUN_DIR_WIN/addon_mlflow_event.json')).get('status', 'UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
        MLFLOW_RUN_ID=$($PYTHON_CMD -c "import json; print(json.load(open('$RUN_DIR_WIN/addon_mlflow_event.json')).get('details', {}).get('mlflow_run_id', ''))" 2>/dev/null || echo "")
    fi
fi

# Run tracing hook if enabled
if [ "$ENABLE_TRACING" = true ]; then
    echo ""
    echo "Tracing hook..."
    TRACING_OUTPUT=$($PYTHON_CMD "$SCRIPT_DIR/addons/trace_hook.py" \
        --card "$CARD_ID" \
        --run_dir "$RUN_DIR_WIN" 2>&1) || true
    echo "$TRACING_OUTPUT"

    # Parse status from addon event
    if [ -f "$RUN_DIR/addon_trace_event.json" ]; then
        TRACING_STATUS=$($PYTHON_CMD -c "import json; print(json.load(open('$RUN_DIR_WIN/addon_trace_event.json')).get('status', 'UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
        TRACE_URL=$($PYTHON_CMD -c "import json; print(json.load(open('$RUN_DIR_WIN/addon_trace_event.json')).get('details', {}).get('trace_url', '') or '')" 2>/dev/null || echo "")
    fi
fi

# Write addon receipt
CREATED_AT=$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)
RECEIPT_FILE="$RUN_DIR/addon_receipt.json"
RECEIPT_TMP="$RECEIPT_FILE.tmp"

cat > "$RECEIPT_TMP" << EOF
{
  "spec_version": "$SPEC_VERSION",
  "receipt_type": "tower_run_plus",
  "created_at": "$CREATED_AT",
  "card_id": "$CARD_ID",
  "run_id": "$RUN_ID",
  "run_dir": "$RUN_DIR",
  "tower_run_exit_code": $TOWER_EXIT_CODE,
  "addons_enabled": {
    "mlflow": $( [ "$ENABLE_MLFLOW" = true ] && echo "true" || echo "false" ),
    "tracing": $( [ "$ENABLE_TRACING" = true ] && echo "true" || echo "false" ),
    "prefect": false
  },
  "addon_results": {
    "mlflow": {
      "status": "$MLFLOW_STATUS",
      "mlflow_run_id": $( [ -n "$MLFLOW_RUN_ID" ] && echo "\"$MLFLOW_RUN_ID\"" || echo "null" ),
      "receipt_path": null
    },
    "tracing": {
      "status": "$TRACING_STATUS",
      "trace_url": $( [ -n "$TRACE_URL" ] && echo "\"$TRACE_URL\"" || echo "null" )
    }
  },
  "command": $(echo "$CMD" | $PYTHON_CMD -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))' 2>/dev/null || echo "\"$CMD\""),
  "session": $( [ -n "$SESSION" ] && echo "\"$SESSION\"" || echo "null" ),
  "model": $( [ -n "$MODEL" ] && echo "\"$MODEL\"" || echo "null" )
}
EOF

sync "$RECEIPT_TMP" 2>/dev/null || true
mv "$RECEIPT_TMP" "$RECEIPT_FILE"

echo ""
echo "============================================================"
echo "Tower Run Plus Complete"
echo "Exit code: $TOWER_EXIT_CODE"
echo "Add-on receipt: $RECEIPT_FILE"
echo "MLflow: $MLFLOW_STATUS"
echo "Tracing: $TRACING_STATUS"
echo "============================================================"

exit $TOWER_EXIT_CODE
