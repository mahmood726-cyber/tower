#!/usr/bin/env bash
#
# SLO-aware merge gate wrapper
#
# Checks merge_freeze.json before delegating to merge_gold.sh
#
# Usage:
#   bash tower/addons/resilience/scripts/tower_merge_gate_slo.sh --card CARD-001
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
CONTROL_DIR="$TOWER_ROOT/control"
MERGE_SCRIPT="$TOWER_ROOT/scripts/merge_gold.sh"

FREEZE_FILE="$CONTROL_DIR/merge_freeze.json"

# Check if merge script exists
if [[ ! -f "$MERGE_SCRIPT" ]]; then
    echo "ERROR: merge_gold.sh not found at: $MERGE_SCRIPT"
    exit 1
fi

# Check freeze status
if [[ -f "$FREEZE_FILE" ]]; then
    # Try to parse with jq
    if command -v jq &> /dev/null; then
        FREEZE_ENABLED=$(jq -r '.freeze_enabled // .status // "false"' "$FREEZE_FILE" 2>/dev/null || echo "false")
        FREEZE_REASON=$(jq -r '.reason // "No reason provided"' "$FREEZE_FILE" 2>/dev/null || echo "")
        FREEZE_UNTIL=$(jq -r '.until // ""' "$FREEZE_FILE" 2>/dev/null || echo "")
    else
        # Fallback: grep
        if grep -q '"freeze_enabled".*true' "$FREEZE_FILE" 2>/dev/null || grep -q '"status".*"ON"' "$FREEZE_FILE" 2>/dev/null; then
            FREEZE_ENABLED="true"
        else
            FREEZE_ENABLED="false"
        fi
        FREEZE_REASON=$(grep -o '"reason"[[:space:]]*:[[:space:]]*"[^"]*"' "$FREEZE_FILE" 2>/dev/null | cut -d'"' -f4 || echo "")
        FREEZE_UNTIL=""
    fi

    if [[ "$FREEZE_ENABLED" == "true" || "$FREEZE_ENABLED" == "ON" ]]; then
        echo "============================================================"
        echo "MERGE FREEZE ACTIVE"
        echo "============================================================"
        echo ""
        echo "Reason: $FREEZE_REASON"
        if [[ -n "$FREEZE_UNTIL" ]]; then
            echo "Until:  $FREEZE_UNTIL"
        fi
        echo ""
        echo "Options:"
        echo "  1. Fix the SLO issues and run: python3 tower/addons/resilience/scripts/tower_error_budget_update.py --write"
        echo "  2. Use merge_gold.sh directly if you must bypass (not recommended)"
        echo ""
        echo "SLO Dashboard: $CONTROL_DIR/slo_dashboard.html"
        echo "============================================================"
        exit 3
    fi
fi

# No freeze, delegate to merge_gold.sh
echo "SLO check passed, delegating to merge_gold.sh..."
exec bash "$MERGE_SCRIPT" "$@"
