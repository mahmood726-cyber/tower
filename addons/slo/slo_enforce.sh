#!/usr/bin/env bash
#
# SLO Enforce - Check SLO status and write recommended actions
#
# Does NOT modify git or merge behavior. Only writes recommendations.
#
# Usage:
#   bash tower/addons/slo/slo_enforce.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
CONTROL_DIR="$TOWER_ROOT/control"

SLO_STATUS_FILE="$CONTROL_DIR/slo_status.json"
ACTIONS_FILE="$CONTROL_DIR/alerts/error_budget_actions.json"
FREEZE_FILE="$CONTROL_DIR/slo_freeze_recommendation.json"

# Ensure alerts directory exists
mkdir -p "$CONTROL_DIR/alerts"

# Check if slo_status.json exists
if [[ ! -f "$SLO_STATUS_FILE" ]]; then
    echo "SLO status file not found: $SLO_STATUS_FILE"
    echo "Run: python3 tower/addons/slo/compute_slo.py --write"
    exit 0
fi

# Check for jq
if command -v jq &> /dev/null; then
    OVERALL_STATUS=$(jq -r '.overall_status // "UNKNOWN"' "$SLO_STATUS_FILE")
else
    # Fallback: simple grep
    if grep -q '"overall_status".*"BREACH"' "$SLO_STATUS_FILE"; then
        OVERALL_STATUS="BREACH"
    elif grep -q '"overall_status".*"WARN"' "$SLO_STATUS_FILE"; then
        OVERALL_STATUS="WARN"
    elif grep -q '"overall_status".*"OK"' "$SLO_STATUS_FILE"; then
        OVERALL_STATUS="OK"
    else
        OVERALL_STATUS="UNKNOWN"
    fi
fi

echo "SLO Overall Status: $OVERALL_STATUS"

if [[ "$OVERALL_STATUS" == "BREACH" ]]; then
    echo ""
    echo "SLO BREACH DETECTED"
    echo "Writing error budget actions to: $ACTIONS_FILE"

    # Get breach details if jq available
    BREACH_REASON="SLO breach detected"
    if command -v jq &> /dev/null; then
        BREACH_METRICS=$(jq -r '.metrics | to_entries[] | select(.value.status == "BREACH") | .key' "$SLO_STATUS_FILE" 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
        if [[ -n "$BREACH_METRICS" ]]; then
            BREACH_REASON="SLO breach: $BREACH_METRICS exceeded threshold"
        fi
    fi

    TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    UNTIL=$(date -u -d "+24 hours" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)

    # Write actions file
    cat > "$ACTIONS_FILE.tmp" << EOF
{
  "spec_version": "v1.5.5",
  "created_at": "$TIMESTAMP",
  "active": true,
  "reason": "$BREACH_REASON",
  "recommended_actions": [
    "Freeze merges for 24h (recommendation only)",
    "Increase PASS audit sampling",
    "Run nightly evals",
    "Open Kaizen proposal"
  ]
}
EOF
    mv "$ACTIONS_FILE.tmp" "$ACTIONS_FILE"

    # Write freeze recommendation
    cat > "$FREEZE_FILE.tmp" << EOF
{
  "spec_version": "v1.5.5",
  "active": true,
  "until": "$UNTIL",
  "reason": "$BREACH_REASON",
  "created_at": "$TIMESTAMP"
}
EOF
    mv "$FREEZE_FILE.tmp" "$FREEZE_FILE"

    echo "Wrote: $ACTIONS_FILE"
    echo "Wrote: $FREEZE_FILE"
    echo ""
    echo "RECOMMENDED ACTIONS:"
    echo "  - Freeze merges for 24h (recommendation only)"
    echo "  - Increase PASS audit sampling"
    echo "  - Run nightly evals"
    echo "  - Open Kaizen proposal"
    echo ""
    echo "View SLO dashboard: $CONTROL_DIR/slo_dashboard.html (if generated)"

elif [[ "$OVERALL_STATUS" == "WARN" ]]; then
    echo ""
    echo "SLO WARNING - Monitor closely"

    # Clear any previous freeze
    if [[ -f "$FREEZE_FILE" ]]; then
        echo "Clearing previous freeze recommendation"
        rm -f "$FREEZE_FILE"
    fi

else
    echo ""
    echo "SLO OK - No action required"

    # Clear any previous freeze/actions
    if [[ -f "$FREEZE_FILE" ]]; then
        echo "Clearing freeze recommendation"
        rm -f "$FREEZE_FILE"
    fi
    if [[ -f "$ACTIONS_FILE" ]]; then
        echo "Clearing error budget actions"
        rm -f "$ACTIONS_FILE"
    fi
fi

exit 0
