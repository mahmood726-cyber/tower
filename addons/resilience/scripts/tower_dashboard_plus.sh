#!/usr/bin/env bash
# tower_dashboard_plus.sh - Overlay Tower dashboard with Resilience & Assurance panel
# Part of Tower v1.5.5 Resilience Add-on
#
# Usage: bash tower/addons/resilience/scripts/tower_dashboard_plus.sh [--no-regenerate]
#
# Creates dashboard_plus.html with status badge overlay
# Does NOT modify any existing Tower scripts

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CONTROL_DIR="$TOWER_ROOT/control"
ADDONS_DIR="$TOWER_ROOT/addons/resilience"
TEMPLATE_FILE="$ADDONS_DIR/templates/resilience_panel_template.html"

# Output files
DASHBOARD_BASE="$CONTROL_DIR/dashboard.html"
DASHBOARD_PLUS="$CONTROL_DIR/dashboard_plus.html"

# Control files to read
MERGE_FREEZE="$CONTROL_DIR/merge_freeze.json"
ERROR_BUDGET="$CONTROL_DIR/error_budget_status.json"
SPC_ALERTS="$CONTROL_DIR/spc_alerts.json"
DRIFT_ALERTS="$CONTROL_DIR/drift_alerts.json"
STATUS_JSON="$CONTROL_DIR/status.json"

# Flags
REGENERATE_BASE=true
if [[ "${1:-}" == "--no-regenerate" ]]; then
    REGENERATE_BASE=false
fi

echo "=== Tower Dashboard Plus ==="
echo "Timestamp: $(date -Iseconds)"

# Step 1: Optionally regenerate base dashboard
if [[ "$REGENERATE_BASE" == "true" ]]; then
    echo ""
    echo "[1/4] Regenerating base dashboard..."
    if [[ -f "$TOWER_ROOT/scripts/tower_dashboard.sh" ]]; then
        bash "$TOWER_ROOT/scripts/tower_dashboard.sh" > /dev/null 2>&1 || {
            echo "  WARNING: Base dashboard generation failed, using existing"
        }
    else
        echo "  WARNING: tower_dashboard.sh not found, using existing dashboard"
    fi
else
    echo ""
    echo "[1/4] Skipping base dashboard regeneration (--no-regenerate)"
fi

# Check base dashboard exists
if [[ ! -f "$DASHBOARD_BASE" ]]; then
    echo "ERROR: Base dashboard not found at $DASHBOARD_BASE"
    exit 1
fi

# Step 2: Read control files and compute status
echo ""
echo "[2/4] Reading control files..."

# Initialize status variables
IS_FROZEN=false
FREEZE_REASON=""
ERROR_BUDGET_REMAINING="N/A"
ERROR_BUDGET_DEPLETED=false
SLO_STATUS="N/A"
SLO_BREACHED=false
SPC_ALERT_COUNT=0
DRIFT_ALERT_COUNT=0
ACTIVE_CARDS=0

# Read merge freeze status
if [[ -f "$MERGE_FREEZE" ]]; then
    IS_FROZEN=$(jq -r '.active // false' "$MERGE_FREEZE" 2>/dev/null || echo "false")
    FREEZE_REASON=$(jq -r '.reason // "Unknown"' "$MERGE_FREEZE" 2>/dev/null || echo "Unknown")
    echo "  - Merge freeze: $IS_FROZEN"
fi

# Read error budget status
if [[ -f "$ERROR_BUDGET" ]]; then
    ERROR_BUDGET_REMAINING=$(jq -r '.remaining_percent // "N/A"' "$ERROR_BUDGET" 2>/dev/null || echo "N/A")
    if [[ "$ERROR_BUDGET_REMAINING" != "N/A" ]]; then
        # Check if depleted (< 0)
        if (( $(echo "$ERROR_BUDGET_REMAINING < 0" | bc -l 2>/dev/null || echo 0) )); then
            ERROR_BUDGET_DEPLETED=true
        fi
        ERROR_BUDGET_REMAINING="${ERROR_BUDGET_REMAINING}%"
    fi
    echo "  - Error budget remaining: $ERROR_BUDGET_REMAINING"
fi

# Read SLO status (from slo addon if available)
SLO_FILE="$CONTROL_DIR/slo_status.json"
if [[ -f "$SLO_FILE" ]]; then
    SLO_STATUS=$(jq -r '.overall_status // "N/A"' "$SLO_FILE" 2>/dev/null || echo "N/A")
    if [[ "$SLO_STATUS" == "BREACHED" ]]; then
        SLO_BREACHED=true
    fi
    echo "  - SLO status: $SLO_STATUS"
fi

# Read SPC alerts
if [[ -f "$SPC_ALERTS" ]]; then
    SPC_ALERT_COUNT=$(jq -r '.alerts | length // 0' "$SPC_ALERTS" 2>/dev/null || echo 0)
    echo "  - SPC alerts: $SPC_ALERT_COUNT"
fi

# Read drift alerts
if [[ -f "$DRIFT_ALERTS" ]]; then
    DRIFT_ALERT_COUNT=$(jq -r '.alerts | length // 0' "$DRIFT_ALERTS" 2>/dev/null || echo 0)
    echo "  - Drift alerts: $DRIFT_ALERT_COUNT"
fi

# Count active cards from status.json
if [[ -f "$STATUS_JSON" ]]; then
    ACTIVE_CARDS=$(jq -r '[.cards[] | select(.state == "ACTIVE")] | length // 0' "$STATUS_JSON" 2>/dev/null || echo 0)
    echo "  - Active cards: $ACTIVE_CARDS"
fi

# Step 3: Compute overall status
echo ""
echo "[3/4] Computing overall status..."

# Priority (highest wins):
# 1. FREEZE if merge_freeze.json exists and active == true
# 2. RED if error_budget < 0 OR SLO breached
# 3. YELLOW if SPC alerts > 0 OR drift alerts > 0
# 4. GREEN if all checks pass
# 5. UNKNOWN otherwise

STATUS="UNKNOWN"
STATUS_LOWER="unknown"

if [[ "$IS_FROZEN" == "true" ]]; then
    STATUS="FREEZE"
    STATUS_LOWER="freeze"
    echo "  Status: FREEZE (reason: $FREEZE_REASON)"
elif [[ "$ERROR_BUDGET_DEPLETED" == "true" ]] || [[ "$SLO_BREACHED" == "true" ]]; then
    STATUS="RED"
    STATUS_LOWER="red"
    echo "  Status: RED (error budget depleted or SLO breached)"
elif [[ "$SPC_ALERT_COUNT" -gt 0 ]] || [[ "$DRIFT_ALERT_COUNT" -gt 0 ]]; then
    STATUS="YELLOW"
    STATUS_LOWER="yellow"
    echo "  Status: YELLOW (SPC alerts: $SPC_ALERT_COUNT, drift alerts: $DRIFT_ALERT_COUNT)"
elif [[ -f "$STATUS_JSON" ]]; then
    STATUS="GREEN"
    STATUS_LOWER="green"
    echo "  Status: GREEN (all systems nominal)"
else
    echo "  Status: UNKNOWN (insufficient data)"
fi

# Build alert tags HTML
ALERT_TAGS=""
if [[ "$IS_FROZEN" == "true" ]]; then
    ALERT_TAGS="$ALERT_TAGS<span class=\"resilience-alert-tag tag-freeze\">FREEZE</span>"
fi
if [[ "$SPC_ALERT_COUNT" -gt 0 ]]; then
    ALERT_TAGS="$ALERT_TAGS<span class=\"resilience-alert-tag tag-spc\">SPC: $SPC_ALERT_COUNT</span>"
fi
if [[ "$DRIFT_ALERT_COUNT" -gt 0 ]]; then
    ALERT_TAGS="$ALERT_TAGS<span class=\"resilience-alert-tag tag-drift\">DRIFT: $DRIFT_ALERT_COUNT</span>"
fi
if [[ "$ERROR_BUDGET_DEPLETED" == "true" ]]; then
    ALERT_TAGS="$ALERT_TAGS<span class=\"resilience-alert-tag tag-budget\">BUDGET DEPLETED</span>"
fi

# Step 4: Generate dashboard plus
echo ""
echo "[4/4] Generating dashboard plus..."

# Read template and substitute placeholders
if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo "ERROR: Template not found at $TEMPLATE_FILE"
    exit 1
fi

TIMESTAMP=$(date -Iseconds)

# Escape special characters for sed
escape_sed() {
    echo "$1" | sed 's/[&/\]/\\&/g'
}

STATUS_ESC=$(escape_sed "$STATUS")
STATUS_LOWER_ESC=$(escape_sed "$STATUS_LOWER")
ERROR_BUDGET_ESC=$(escape_sed "$ERROR_BUDGET_REMAINING")
SLO_STATUS_ESC=$(escape_sed "$SLO_STATUS")
ACTIVE_CARDS_ESC=$(escape_sed "$ACTIVE_CARDS")
TIMESTAMP_ESC=$(escape_sed "$TIMESTAMP")
ALERT_TAGS_ESC=$(echo "$ALERT_TAGS" | sed 's/[&/\]/\\&/g')

PANEL_HTML=$(cat "$TEMPLATE_FILE" | \
    sed "s#{{STATUS}}#$STATUS_ESC#g" | \
    sed "s#{{STATUS_LOWER}}#$STATUS_LOWER_ESC#g" | \
    sed "s#{{ERROR_BUDGET_REMAINING}}#$ERROR_BUDGET_ESC#g" | \
    sed "s#{{SLO_STATUS}}#$SLO_STATUS_ESC#g" | \
    sed "s#{{ACTIVE_CARDS}}#$ACTIVE_CARDS_ESC#g" | \
    sed "s#{{ALERT_TAGS}}#$ALERT_TAGS_ESC#g" | \
    sed "s#{{TIMESTAMP}}#$TIMESTAMP_ESC#g")

# Read base dashboard and inject panel after <body>
# Use awk to insert after first <body> or <body ...> tag
awk -v panel="$PANEL_HTML" '
    /<body[^>]*>/ && !inserted {
        print
        print panel
        inserted = 1
        next
    }
    { print }
' "$DASHBOARD_BASE" > "$DASHBOARD_PLUS.tmp"

# Atomic write
mv "$DASHBOARD_PLUS.tmp" "$DASHBOARD_PLUS"

echo ""
echo "=== Dashboard Plus Complete ==="
echo "Status: $STATUS"
echo "Output: $DASHBOARD_PLUS"
echo ""

# Summary JSON for automation
cat > "$CONTROL_DIR/dashboard_plus_status.json" << EOF
{
  "generated_at": "$TIMESTAMP",
  "status": "$STATUS",
  "is_frozen": $IS_FROZEN,
  "freeze_reason": "$FREEZE_REASON",
  "error_budget_remaining": "$ERROR_BUDGET_REMAINING",
  "error_budget_depleted": $ERROR_BUDGET_DEPLETED,
  "slo_status": "$SLO_STATUS",
  "slo_breached": $SLO_BREACHED,
  "spc_alert_count": $SPC_ALERT_COUNT,
  "drift_alert_count": $DRIFT_ALERT_COUNT,
  "active_cards": $ACTIVE_CARDS,
  "output_file": "$DASHBOARD_PLUS"
}
EOF

echo "Status file: $CONTROL_DIR/dashboard_plus_status.json"
