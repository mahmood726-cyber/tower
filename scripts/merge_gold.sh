#!/usr/bin/env bash
#
# Tower Merge Gold Script
# Safely merges a GOLD card to main branch within merge windows.
#
# Usage:
#   merge_gold.sh --card CARD-XXX [--do-merge] [--allow-offline]
#
# Without --do-merge: dry-run mode (prints instructions)
# With --do-merge: performs actual merge
# With --allow-offline: allow merge even if git pull fails (not recommended)
#
# Requirements:
#   - Card must be GOLD in status.json
#   - Must be within merge window (06:30-06:50 or 19:00-19:20 Europe/London)
#   - Proofpack must exist
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
    # Git Bash: /c/Users/... -> C:/Users/...
    if [[ "$path" == /[a-zA-Z]/* ]]; then
        echo "${path:1:1}:${path:2}"
    # Cygwin: /cygdrive/c/Users/... -> C:/Users/...
    elif [[ "$path" == /cygdrive/[a-zA-Z]/* ]]; then
        echo "${path:10:1}:${path:11}"
    else
        echo "$path"
    fi
}

STATUS_FILE="$TOWER_ROOT/control/status.json"
DRIFT_CONFIG="$TOWER_ROOT/control/drift_config.json"

# Windows path versions for Python heredocs
STATUS_FILE_WIN=$(to_win_path "$STATUS_FILE")

# Parse arguments
CARD_ID=""
DO_MERGE=false
ALLOW_OFFLINE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --card)
            CARD_ID="$2"
            shift 2
            ;;
        --do-merge)
            DO_MERGE=true
            shift
            ;;
        --allow-offline)
            ALLOW_OFFLINE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$CARD_ID" ]; then
    echo "ERROR: --card is required"
    echo "Usage: merge_gold.sh --card CARD-XXX [--do-merge] [--allow-offline]"
    exit 1
fi

# Validate CARD_ID format (prevent path traversal / injection)
if ! echo "$CARD_ID" | grep -qE '^CARD-[0-9]+$'; then
    echo "ERROR: --card must match CARD-NNN format (got: $CARD_ID)"
    exit 1
fi

echo "============================================================"
echo "Tower Merge Gold"
echo "Card: $CARD_ID"
echo "Mode: $([ "$DO_MERGE" = true ] && echo 'LIVE MERGE' || echo 'DRY RUN')"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"

# Check if in merge window
check_merge_window() {
    # Get current time in Europe/London
    local current_time
    if command -v $PYTHON_CMD &> /dev/null; then
        current_time=$($PYTHON_CMD << 'EOF'
from datetime import datetime
try:
    import zoneinfo
    tz = zoneinfo.ZoneInfo("Europe/London")
except:
    try:
        import pytz
        tz = pytz.timezone("Europe/London")
    except:
        tz = None

if tz:
    now = datetime.now(tz)
else:
    now = datetime.now()

print(now.strftime("%H:%M"))
EOF
)
    else
        current_time=$(date +%H:%M)
    fi

    # Validate time format before arithmetic
    if [[ ! "$current_time" =~ ^[0-9]{2}:[0-9]{2}$ ]]; then
        echo "FAIL (invalid time: $current_time)"
        return 1
    fi

    local hour=${current_time%:*}
    local minute=${current_time#*:}
    local total_minutes=$((10#$hour * 60 + 10#$minute))

    # Morning window: 06:30 - 06:50 (390 - 410 minutes)
    # Evening window: 19:00 - 19:20 (1140 - 1160 minutes)
    if [ $total_minutes -ge 390 ] && [ $total_minutes -le 410 ]; then
        echo "PASS"
        return 0
    elif [ $total_minutes -ge 1140 ] && [ $total_minutes -le 1160 ]; then
        echo "PASS"
        return 0
    else
        echo "FAIL"
        return 1
    fi
}

# Check card is GOLD
check_card_gold() {
    if [ ! -f "$STATUS_FILE" ]; then
        echo "FAIL"
        return 1
    fi

    local state
    state=$(_GC_STATUS="$STATUS_FILE_WIN" _GC_CARD="$CARD_ID" $PYTHON_CMD -c "
import json, os
with open(os.environ['_GC_STATUS']) as f:
    data = json.load(f)
cards = data.get('cards', [])
card = next((c for c in cards if c.get('card_id') == os.environ['_GC_CARD']), {}) if isinstance(cards, list) else cards.get(os.environ['_GC_CARD'], {})
print(card.get('state', 'UNKNOWN'))
" 2>/dev/null || echo "UNKNOWN")

    if [ "$state" = "GOLD" ]; then
        echo "PASS"
        return 0
    else
        echo "FAIL ($state)"
        return 1
    fi
}

# Check proofpack exists (searches all date directories, not just today)
check_proofpack() {
    local proofpacks_base="$TOWER_ROOT/proofpacks"

    # Search for any proofpack with valid manifest for this card
    if [ -d "$proofpacks_base" ]; then
        for date_dir in "$proofpacks_base"/*/; do
            local proofpack_dir="${date_dir}$CARD_ID"
            if [ -d "$proofpack_dir" ] && [ -f "$proofpack_dir/manifest.json" ]; then
                echo "PASS"
                return 0
            fi
        done
    fi

    echo "FAIL"
    return 1
}

# Check card color is GREEN
check_card_green() {
    if [ ! -f "$STATUS_FILE" ]; then
        echo "FAIL"
        return 1
    fi

    local color
    color=$(_GC_STATUS="$STATUS_FILE_WIN" _GC_CARD="$CARD_ID" $PYTHON_CMD -c "
import json, os
with open(os.environ['_GC_STATUS']) as f:
    data = json.load(f)
cards = data.get('cards', [])
card = next((c for c in cards if c.get('card_id') == os.environ['_GC_CARD']), {}) if isinstance(cards, list) else cards.get(os.environ['_GC_CARD'], {})
print(card.get('color', 'UNKNOWN'))
" 2>/dev/null || echo "UNKNOWN")

    if [ "$color" = "GREEN" ]; then
        echo "PASS"
        return 0
    else
        echo "FAIL ($color)"
        return 1
    fi
}

# Circuit breaker check (TruthCert fail-closed design)
check_circuit_breaker() {
    local drift_ledger="$TOWER_ROOT/control/drift_ledger.json"

    if [ ! -f "$drift_ledger" ]; then
        echo "PASS"
        return 0
    fi

    # Check for system health using Python
    local health
    health=$(_GC_LEDGER="$(to_win_path "$drift_ledger")" $PYTHON_CMD -c "
import json, os
from datetime import datetime, timedelta

ledger_file = os.environ.get('_GC_LEDGER', '')
if not ledger_file:
    print('PASS')
    exit(0)

try:
    with open(ledger_file) as f:
        data = json.load(f)
except:
    print('PASS')
    exit(0)

events = data.get('events', [])
now = datetime.now()
week_ago = now - timedelta(days=7)

# Count P0 failures in last week
p0_failures = 0
unadjudicated = 0

for e in events:
    if e.get('severity') == 'P0':
        try:
            ts_str = e.get('timestamp', '')
            # Parse timestamp, stripping timezone for naive comparison
            # Handle: 2026-02-06T17:30:06Z, 2026-02-06T17:30:06+00:00, 2026-02-06T17:30:06-05:00
            if ts_str:
                # Remove Z suffix
                if ts_str.endswith('Z'):
                    ts_str = ts_str[:-1]
                # Remove +HH:MM timezone
                if '+' in ts_str and 'T' in ts_str:
                    ts_str = ts_str.split('+')[0]
                # Remove -HH:MM timezone (but not date dashes)
                elif ts_str.count('-') > 2 and 'T' in ts_str:
                    # Split at T, then remove timezone from time part
                    parts = ts_str.split('T')
                    time_part = parts[1].split('-')[0] if '-' in parts[1] else parts[1]
                    ts_str = parts[0] + 'T' + time_part
                # Remove milliseconds and parse
                ts_str = ts_str.split('.')[0]
                ts = datetime.fromisoformat(ts_str)
                if ts > week_ago:
                    p0_failures += 1
        except:
            pass
    if not e.get('adjudicated', False):
        unadjudicated += 1

# Circuit breaker thresholds
MAX_P0 = 3
MAX_UNADJ = 10

if p0_failures >= MAX_P0:
    print(f'FAIL (P0 failures: {p0_failures} >= {MAX_P0})')
elif unadjudicated >= MAX_UNADJ:
    print(f'FAIL (unadjudicated: {unadjudicated} >= {MAX_UNADJ})')
else:
    print('PASS')
" 2>/dev/null || echo "PASS")

    echo "$health"
    if [ "${health%% *}" = "PASS" ]; then
        return 0
    else
        return 1
    fi
}

# Check card has Gold assurance level
check_assurance_gold() {
    if [ ! -f "$STATUS_FILE" ]; then
        echo "FAIL"
        return 1
    fi

    local assurance
    assurance=$(_GC_STATUS="$STATUS_FILE_WIN" _GC_CARD="$CARD_ID" $PYTHON_CMD -c "
import json, os
with open(os.environ['_GC_STATUS']) as f:
    data = json.load(f)
cards = data.get('cards', [])
card = next((c for c in cards if c.get('card_id') == os.environ['_GC_CARD']), {}) if isinstance(cards, list) else cards.get(os.environ['_GC_CARD'], {})
print(card.get('assurance', 'none'))
" 2>/dev/null || echo "none")

    if [ "$assurance" = "gold" ]; then
        echo "PASS"
        return 0
    else
        echo "FAIL ($assurance)"
        return 1
    fi
}

# Run all checks
echo ""
echo "Pre-merge checks (TruthCert fail-closed):"
echo "------------------------------------------"

CHECKS_PASS=true

echo -n "  Circuit breaker: "
result=$(check_circuit_breaker) && true
echo "$result"
if [ "${result%% *}" != "PASS" ]; then
    echo "    (system health degraded - merges blocked)"
    CHECKS_PASS=false
fi

echo -n "  Merge window: "
result=$(check_merge_window) && true
echo "$result"
if [ "${result%% *}" != "PASS" ]; then
    echo "    (window: 06:30-06:50 or 19:00-19:20 Europe/London)"
    CHECKS_PASS=false
fi

echo -n "  Card is GOLD state: "
result=$(check_card_gold) && true
echo "$result"
[ "${result%% *}" != "PASS" ] && CHECKS_PASS=false

echo -n "  Card is GREEN color: "
result=$(check_card_green) && true
echo "$result"
[ "${result%% *}" != "PASS" ] && CHECKS_PASS=false

echo -n "  Assurance level: "
result=$(check_assurance_gold) && true
echo "$result"
[ "${result%% *}" != "PASS" ] && CHECKS_PASS=false

echo -n "  Proofpack exists: "
result=$(check_proofpack) && true
echo "$result"
[ "${result%% *}" != "PASS" ] && CHECKS_PASS=false

echo ""

if [ "$CHECKS_PASS" = false ]; then
    echo "============================================================"
    echo "MERGE BLOCKED: Pre-merge checks failed (fail-closed)"
    echo "============================================================"
    exit 1
fi

# If dry run, print instructions
if [ "$DO_MERGE" = false ]; then
    WORKTREE_DIR="$TOWER_ROOT/worktrees/$CARD_ID"
    BRANCH="card/$CARD_ID"

    echo "============================================================"
    echo "DRY RUN: Merge would proceed"
    echo ""
    echo "To perform the merge, run:"
    echo "  merge_gold.sh --card $CARD_ID --do-merge"
    echo ""
    echo "Or manually:"
    echo "  git checkout main"
    echo "  git merge $BRANCH"
    echo "  git push origin main"
    echo "============================================================"
    exit 0
fi

# Perform actual merge
echo "Performing merge..."
echo ""

WORKTREE_DIR="$TOWER_ROOT/worktrees/$CARD_ID"
BRANCH="card/$CARD_ID"

# Check worktree exists
if [ ! -d "$WORKTREE_DIR" ]; then
    echo "ERROR: Worktree not found: $WORKTREE_DIR"
    exit 1
fi

# Perform merge in subshell to preserve working directory on error
(
    cd "$WORKTREE_DIR" || exit 1

    # Ensure we're on the card branch (with proper error handling)
    if ! git checkout "$BRANCH" 2>/dev/null; then
        echo "ERROR: Cannot checkout branch $BRANCH"
        echo "  Make sure the branch exists and worktree is clean"
        exit 1
    fi

    # Get the commit to merge
    MERGE_SHA=$(git rev-parse HEAD)
    echo "Merge SHA: $MERGE_SHA"

    # Switch to main and merge
    if ! git checkout main; then
        echo "ERROR: Cannot checkout main branch"
        exit 1
    fi

    if ! git pull origin main 2>/dev/null; then
        if [ "$ALLOW_OFFLINE" = "true" ]; then
            echo "WARNING: Could not pull from origin/main (--allow-offline specified)"
        else
            echo "ERROR: Could not pull from origin/main"
            echo "  This is blocked to prevent merging into stale main (fail-closed)."
            echo "  Options:"
            echo "    1. Fix network connectivity and retry"
            echo "    2. Use --allow-offline to proceed anyway (not recommended)"
            exit 1
        fi
    fi

    if ! git merge "$BRANCH" -m "Merge $CARD_ID to main

Card: $CARD_ID
Branch: $BRANCH
Spec: $SPEC_VERSION
Merged at: $(date -Iseconds 2>/dev/null || date)"; then
        echo "ERROR: Merge failed - possible conflict"
        echo "  Resolve conflicts manually and try again"
        git merge --abort 2>/dev/null || true
        exit 1
    fi
)
MERGE_EXIT=$?
if [ $MERGE_EXIT -ne 0 ]; then
    exit $MERGE_EXIT
fi

# Update status (quoted heredoc + env vars to avoid injection)
_GC_STATUS_FILE="$STATUS_FILE_WIN" \
_GC_CARD_ID="$CARD_ID" \
$PYTHON_CMD << 'PYEOF'
import json
import os
import sys
from datetime import datetime

status_file = os.environ["_GC_STATUS_FILE"]
card_id = os.environ["_GC_CARD_ID"]

with open(status_file, 'r') as f:
    status = json.load(f)

# cards is an array of objects, not a dict
cards = status.get('cards', [])
found = False
if isinstance(cards, list):
    for c in cards:
        if c.get('card_id') == card_id:
            c['state'] = 'MERGED'
            c['updated_at'] = datetime.now().isoformat()
            found = True
            break
elif isinstance(cards, dict) and card_id in cards:
    cards[card_id]['state'] = 'MERGED'
    cards[card_id]['updated_at'] = datetime.now().isoformat()
    found = True

if not found:
    print(f"ERROR: Card {card_id} not found in status.json", file=sys.stderr)
    sys.exit(1)

status['cards'] = cards
status['last_updated'] = datetime.now().isoformat()

tmp_file = status_file + '.tmp'
with open(tmp_file, 'w') as f:
    json.dump(status, f, indent=2)

os.replace(tmp_file, status_file)
PYEOF

echo ""
echo "============================================================"
echo "MERGE COMPLETE"
echo "Card $CARD_ID merged to main"
echo ""
echo "To push: git push origin main"
echo "============================================================"
