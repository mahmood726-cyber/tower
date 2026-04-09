#!/usr/bin/env bash
# tower_with_ledger.sh - Wrapper that logs Tower command execution to event ledger
# Part of Tower v1.5.5 Ledger Add-on
#
# Usage:
#   bash tower/addons/ledger/tower_with_ledger.sh <tower_script> [args...]
#
# Examples:
#   bash tower/addons/ledger/tower_with_ledger.sh tower/scripts/tower_gatecheck.sh CARD-042
#   bash tower/addons/ledger/tower_with_ledger.sh tower/scripts/tower_dashboard.sh
#
# This wrapper:
#   1. Logs a "command.started" event
#   2. Runs the specified Tower script
#   3. Logs a "command.completed" or "command.failed" event with exit code

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/log_event.sh"

# Check arguments
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <tower_script> [args...]"
    echo ""
    echo "Wraps any Tower script with automatic event logging."
    exit 1
fi

TOWER_SCRIPT="$1"
shift
TOWER_ARGS=("$@")

# Extract script name for logging
SCRIPT_NAME=$(basename "$TOWER_SCRIPT" .sh)

# Try to extract card ID from arguments
CARD_ID=""
for arg in "${TOWER_ARGS[@]:-}"; do
    if [[ "$arg" =~ ^CARD-[0-9]+ ]]; then
        CARD_ID="$arg"
        break
    fi
done

# Log start event
START_TIME=$(date +%s.%N)
export TOWER_ACTOR="tower_with_ledger:$SCRIPT_NAME"

log_event "command.started" "$CARD_ID" "$(jq -n \
    --arg script "$TOWER_SCRIPT" \
    --argjson args "$(printf '%s\n' "${TOWER_ARGS[@]:-}" | jq -R . | jq -s .)" \
    '{script: $script, args: $args}'
)" > /dev/null

# Run the actual command
EXIT_CODE=0
set +e
"$TOWER_SCRIPT" "${TOWER_ARGS[@]:-}"
EXIT_CODE=$?
set -e

# Calculate duration
END_TIME=$(date +%s.%N)
DURATION=$(echo "$END_TIME - $START_TIME" | bc 2>/dev/null || echo "0")

# Log completion event
if [[ $EXIT_CODE -eq 0 ]]; then
    log_event "command.completed" "$CARD_ID" "$(jq -n \
        --arg script "$TOWER_SCRIPT" \
        --arg duration "$DURATION" \
        '{script: $script, exit_code: 0, duration_seconds: ($duration | tonumber)}'
    )" > /dev/null
else
    log_event "command.failed" "$CARD_ID" "$(jq -n \
        --arg script "$TOWER_SCRIPT" \
        --argjson exit "$EXIT_CODE" \
        --arg duration "$DURATION" \
        '{script: $script, exit_code: $exit, duration_seconds: ($duration | tonumber)}'
    )" > /dev/null
fi

# Exit with original exit code
exit $EXIT_CODE
