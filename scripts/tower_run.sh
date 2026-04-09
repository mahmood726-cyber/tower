#!/usr/bin/env bash
#
# Tower Run Wrapper
# Wraps command execution with tracking, heartbeat, and artifact generation.
#
# Usage:
#   tower_run.sh --card CARD-XXX --session apps_dev1 --model claude_opus --cmd "<command>"
#
# Creates:
#   - tower/artifacts/YYYY-MM-DD/CARD-XXX/run_<run_id>/
#     - run_context.json
#     - stdout.log
#     - stderr.log
#     - heartbeat (updated every 60s)
#     - run_summary.json (on exit)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$SCRIPT_DIR")"
SPEC_VERSION="v1.5.7"

# Detect Python command (python3 or python)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Neither python3 nor python found"
    exit 1
fi

# Parse arguments
CARD_ID=""
SESSION=""
MODEL=""
CMD=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --card)
            CARD_ID="$2"
            shift 2
            ;;
        --session)
            SESSION="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
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

# Validate required arguments
if [ -z "$CARD_ID" ]; then
    echo "ERROR: --card is required"
    echo "Usage: tower_run.sh --card CARD-XXX --session apps_dev1 --model claude_opus --cmd \"<command>\""
    exit 1
fi

# Validate CARD_ID format (prevent path traversal / injection)
if ! echo "$CARD_ID" | grep -qE '^CARD-[0-9]+$'; then
    echo "ERROR: --card must match CARD-NNN format (got: $CARD_ID)"
    exit 1
fi

if [ -z "$CMD" ]; then
    echo "ERROR: --cmd is required"
    exit 1
fi

# Generate run_id: YYYYMMDD_HHMMSS_random
DATE_PART=$(date +%Y%m%d_%H%M%S)
# Use Python for portable randomness since xxd/shuf may not be available
RANDOM_PART=$($PYTHON_CMD -c "import random; print(f'{random.randint(0,0xFFFFFFFF):08x}')" 2>/dev/null || printf '%08x' $((RANDOM * 65536 + RANDOM)))
RUN_ID="${DATE_PART}_${RANDOM_PART}"

# Create artifacts directory
DATE_DIR=$(date +%Y-%m-%d)
ARTIFACTS_DIR="$TOWER_ROOT/artifacts/$DATE_DIR/$CARD_ID/run_$RUN_ID"
mkdir -p "$ARTIFACTS_DIR"

# Get git info
GIT_SHA=""
GIT_BRANCH=""
if command -v git &> /dev/null && git rev-parse --git-dir &> /dev/null; then
    GIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "")
    GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
fi

# Get machine info
MACHINE_ID="laptop"
if [ -n "$TOWER_MACHINE" ]; then
    MACHINE_ID="$TOWER_MACHINE"
fi

# Start time
START_TIME=$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)
START_EPOCH=$(date +%s)

# Write run_context.json (atomic write)
CONTEXT_TMP="$ARTIFACTS_DIR/.run_context.json.tmp"
CONTEXT_FILE="$ARTIFACTS_DIR/run_context.json"

cat > "$CONTEXT_TMP" << EOF
{
  "run_id": "$RUN_ID",
  "card_id": "$CARD_ID",
  "session": ${SESSION:+\"$SESSION\"}${SESSION:-null},
  "model": ${MODEL:+\"$MODEL\"}${MODEL:-null},
  "command": $(echo "$CMD" | $PYTHON_CMD -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))' 2>/dev/null || echo "\"$(echo "$CMD" | sed 's/\\/\\\\/g; s/"/\\"/g')\""),
  "start_time": "$START_TIME",
  "working_dir": "$(pwd)",
  "git_sha": ${GIT_SHA:+\"$GIT_SHA\"}${GIT_SHA:-null},
  "git_branch": ${GIT_BRANCH:+\"$GIT_BRANCH\"}${GIT_BRANCH:-null},
  "spec_version": "$SPEC_VERSION",
  "machine": "$MACHINE_ID",
  "environment": {}
}
EOF

# Atomic move
sync "$CONTEXT_TMP" 2>/dev/null || true
mv "$CONTEXT_TMP" "$CONTEXT_FILE"

echo "============================================================"
echo "Tower Run Started"
echo "Run ID: $RUN_ID"
echo "Card: $CARD_ID"
echo "Session: ${SESSION:-N/A}"
echo "Model: ${MODEL:-N/A}"
echo "Artifacts: $ARTIFACTS_DIR"
echo "============================================================"

# Heartbeat function
HEARTBEAT_FILE="$ARTIFACTS_DIR/heartbeat"
HEARTBEAT_PID=""

start_heartbeat() {
    (
        while true; do
            echo "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)" > "$HEARTBEAT_FILE.tmp"
            mv "$HEARTBEAT_FILE.tmp" "$HEARTBEAT_FILE"
            sleep 60
        done
    ) &
    HEARTBEAT_PID=$!
}

stop_heartbeat() {
    if [ -n "$HEARTBEAT_PID" ]; then
        kill "$HEARTBEAT_PID" 2>/dev/null || true
        wait "$HEARTBEAT_PID" 2>/dev/null || true
        # Clean up any leftover temp file from heartbeat
        rm -f "$HEARTBEAT_FILE.tmp" 2>/dev/null || true
    fi
}

# Store exit code for cleanup trap (set before execution, updated after)
FINAL_EXIT_CODE=1

# Cleanup on exit
cleanup() {
    # Capture $? FIRST before any other statement (local resets $?)
    local saved_exit=$?
    local exit_code=${FINAL_EXIT_CODE:-$saved_exit}
    stop_heartbeat

    # Calculate duration
    END_EPOCH=$(date +%s)
    DURATION=$((END_EPOCH - START_EPOCH))
    END_TIME=$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)

    # Write run_summary.json (atomic)
    SUMMARY_TMP="$ARTIFACTS_DIR/.run_summary.json.tmp"
    SUMMARY_FILE="$ARTIFACTS_DIR/run_summary.json"

    cat > "$SUMMARY_TMP" << EOF
{
  "run_id": "$RUN_ID",
  "card_id": "$CARD_ID",
  "exit_code": $exit_code,
  "start_time": "$START_TIME",
  "end_time": "$END_TIME",
  "duration_seconds": $DURATION,
  "spec_version": "$SPEC_VERSION"
}
EOF

    sync "$SUMMARY_TMP" 2>/dev/null || true
    mv "$SUMMARY_TMP" "$SUMMARY_FILE"

    echo ""
    echo "============================================================"
    echo "Tower Run Completed"
    echo "Exit code: $exit_code"
    echo "Duration: ${DURATION}s"
    echo "Summary: $SUMMARY_FILE"
    echo "============================================================"
}

trap cleanup EXIT

# Start heartbeat
start_heartbeat

# Execute command and capture output
echo ""
echo "Executing: $CMD"
echo "------------------------------------------------------------"

# Run command with output capture (bash -c for subprocess isolation instead of eval)
# Note: Process substitution can lose exit codes on some bash versions
# Use direct file output + tail display for reliability
#
# SECURITY NOTE (tower_run.sh command execution):
# This script intentionally executes arbitrary commands via bash -c "$CMD".
# This is by design: tower_run.sh is the user-facing "run" command that executes
# user-specified commands within a card's context (worktree isolation, artifact
# capture, exit code tracking). The command comes from the authenticated user
# or from explicitly authored cards in status.json.
#
# Safeguards:
#   1. Card ID validation (CARD-NNN format only) prevents path traversal
#   2. Worktree isolation contains file operations to card-specific directories
#   3. All execution is logged with full provenance in run_context.json
#   4. Exit codes and outputs are captured for audit trail
#
# For batch/automated execution, use night_runner.sh which has allowlist/blocklist
# validation. tower_run.sh is the low-level executor trusted with user commands.
set +e

# Create log files FIRST to avoid race condition with tail
touch "$ARTIFACTS_DIR/stdout.log" "$ARTIFACTS_DIR/stderr.log"

# Start tail processes BEFORE the command to capture all output
tail -f "$ARTIFACTS_DIR/stdout.log" 2>/dev/null &
TAIL_STDOUT_PID=$!
tail -f "$ARTIFACTS_DIR/stderr.log" >&2 2>/dev/null &
TAIL_STDERR_PID=$!

# Small delay to ensure tail is ready
sleep 0.1 2>/dev/null || true

# Now start the command
bash -c "$CMD" > "$ARTIFACTS_DIR/stdout.log" 2> "$ARTIFACTS_DIR/stderr.log" &
CMD_PID=$!

# Wait for command to finish
wait $CMD_PID
EXIT_CODE=$?
FINAL_EXIT_CODE=$EXIT_CODE

# Stop tail processes
kill $TAIL_STDOUT_PID 2>/dev/null || true
kill $TAIL_STDERR_PID 2>/dev/null || true
wait $TAIL_STDOUT_PID 2>/dev/null || true
wait $TAIL_STDERR_PID 2>/dev/null || true
set -e

exit $EXIT_CODE
