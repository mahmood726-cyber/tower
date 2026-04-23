#!/usr/bin/env bash
#
# Tower Drift Watchdog
# Monitors active sessions/cards for drift and writes alerts.
#
# Usage:
#   tower_watchdog.sh [--once]
#
# Without --once: runs continuously
# With --once: single check and exit
#
# Checks:
#   - No artifacts for threshold minutes
#   - Heartbeat stale > threshold
#
# Output:
#   tower/control/alerts/drift_alerts.json
#   tower/control/alerts/drift_log.csv
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
        # Convert /<drive>/Users/... to <drive>:/Users/... (keep forward slashes for Python)
        echo "${path:1:1}:${path:2}"
    else
        echo "$path"
    fi
}

DRIFT_CONFIG="$TOWER_ROOT/control/drift_config.json"
STATUS_FILE="$TOWER_ROOT/control/status.json"
ALERTS_FILE="$TOWER_ROOT/control/alerts/drift_alerts.json"
DRIFT_LOG="$TOWER_ROOT/control/alerts/drift_log.csv"

# Windows path versions for Python heredocs
DRIFT_CONFIG_WIN=$(to_win_path "$DRIFT_CONFIG")
STATUS_FILE_WIN=$(to_win_path "$STATUS_FILE")

# Parse arguments
ONCE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --once)
            ONCE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Ensure alerts directory exists
mkdir -p "$TOWER_ROOT/control/alerts"

# Initialize drift log if not exists
if [ ! -f "$DRIFT_LOG" ]; then
    echo "timestamp,card_id,alert_type,message" > "$DRIFT_LOG"
fi

# Rate limiting: track last alert per card
RATE_LIMIT_FILE="$TOWER_ROOT/control/alerts/.rate_limit"
touch "$RATE_LIMIT_FILE"

echo "============================================================"
echo "Tower Drift Watchdog"
echo "Mode: $([ "$ONCE" = true ] && echo 'single check' || echo 'continuous')"
echo "Config: $DRIFT_CONFIG"
echo "============================================================"

# Load configuration
load_config() {
    if [ -f "$DRIFT_CONFIG" ]; then
        INTERACTIVE_THRESHOLD=$($PYTHON_CMD -c "import json; print(json.load(open('$DRIFT_CONFIG_WIN')).get('thresholds', {}).get('interactive', 20))" 2>/dev/null || echo 20)
        PIPELINE_THRESHOLD=$($PYTHON_CMD -c "import json; print(json.load(open('$DRIFT_CONFIG_WIN')).get('thresholds', {}).get('pipeline', 30))" 2>/dev/null || echo 30)
        BATCH_THRESHOLD=$($PYTHON_CMD -c "import json; print(json.load(open('$DRIFT_CONFIG_WIN')).get('thresholds', {}).get('batch', 60))" 2>/dev/null || echo 60)
        HEARTBEAT_STALE=$($PYTHON_CMD -c "import json; print(json.load(open('$DRIFT_CONFIG_WIN')).get('heartbeat', {}).get('stale_threshold_seconds', 120))" 2>/dev/null || echo 120)
        RATE_LIMIT=$($PYTHON_CMD -c "import json; print(json.load(open('$DRIFT_CONFIG_WIN')).get('alert_rate_limit', {}).get('per_card_per_hour', 1))" 2>/dev/null || echo 1)
    else
        INTERACTIVE_THRESHOLD=20
        PIPELINE_THRESHOLD=30
        BATCH_THRESHOLD=60
        HEARTBEAT_STALE=120
        RATE_LIMIT=1
    fi
}

# Check if rate limited
is_rate_limited() {
    local card_id="$1"
    local now=$(date +%s)
    local last_alert=$(grep "^$card_id:" "$RATE_LIMIT_FILE" | cut -d: -f2 || echo 0)

    if [ -n "$last_alert" ] && [ $((now - last_alert)) -lt 3600 ]; then
        return 0  # Rate limited
    fi
    return 1  # Not rate limited
}

# Update rate limit
update_rate_limit() {
    local card_id="$1"
    local now=$(date +%s)

    # Remove old entry
    grep -v "^$card_id:" "$RATE_LIMIT_FILE" > "$RATE_LIMIT_FILE.tmp" || true
    echo "$card_id:$now" >> "$RATE_LIMIT_FILE.tmp"
    mv "$RATE_LIMIT_FILE.tmp" "$RATE_LIMIT_FILE"
}

# Check for drift
check_drift() {
    local now=$(date +%s)
    local today=$(date +%Y-%m-%d)
    local alerts=()

    # Get active cards
    if [ ! -f "$STATUS_FILE" ]; then
        return
    fi

    local active_cards=$($PYTHON_CMD -c "
import json
with open('$STATUS_FILE_WIN') as f:
    data = json.load(f)
for card_id, card in data.get('cards', {}).items():
    if card.get('state') == 'ACTIVE':
        print(card_id)
" 2>/dev/null || true)

    for card_id in $active_cards; do
        if is_rate_limited "$card_id"; then
            continue
        fi

        local card_artifacts="$TOWER_ROOT/artifacts/$today/$card_id"

        # Check for recent artifacts
        local latest_artifact=0
        if [ -d "$card_artifacts" ]; then
            for run_dir in "$card_artifacts"/run_*/; do
                if [ -d "$run_dir" ]; then
                    # Check run_summary for completion
                    if [ -f "$run_dir/run_summary.json" ]; then
                        local run_time=$(stat -c %Y "$run_dir/run_summary.json" 2>/dev/null || stat -f %m "$run_dir/run_summary.json" 2>/dev/null || echo 0)
                        [ $run_time -gt $latest_artifact ] && latest_artifact=$run_time
                    fi

                    # Check heartbeat
                    if [ -f "$run_dir/heartbeat" ]; then
                        local hb_time=$(stat -c %Y "$run_dir/heartbeat" 2>/dev/null || stat -f %m "$run_dir/heartbeat" 2>/dev/null || echo 0)

                        if [ $((now - hb_time)) -gt $HEARTBEAT_STALE ]; then
                            local message="Heartbeat stale for $card_id (last: $((now - hb_time))s ago)"
                            echo "DRIFT: $message"
                            alerts+=("{\"card_id\": \"$card_id\", \"type\": \"heartbeat_stale\", \"message\": \"$message\", \"timestamp\": \"$(date -Iseconds)\"}")
                            echo "$(date -Iseconds),$card_id,heartbeat_stale,\"$message\"" >> "$DRIFT_LOG"
                            update_rate_limit "$card_id"
                        fi
                    fi
                fi
            done
        fi

        # Check for no activity
        local minutes_since_activity=$(( (now - latest_artifact) / 60 ))
        if [ $latest_artifact -gt 0 ] && [ $minutes_since_activity -gt $INTERACTIVE_THRESHOLD ]; then
            local message="No activity for $card_id ($minutes_since_activity min)"
            echo "DRIFT: $message"
            alerts+=("{\"card_id\": \"$card_id\", \"type\": \"no_activity\", \"message\": \"$message\", \"timestamp\": \"$(date -Iseconds)\"}")
            echo "$(date -Iseconds),$card_id,no_activity,\"$message\"" >> "$DRIFT_LOG"
            update_rate_limit "$card_id"
        fi
    done

    # Write alerts file
    if [ ${#alerts[@]} -gt 0 ]; then
        local alerts_json="[$(IFS=,; echo "${alerts[*]}")]"
        echo "$alerts_json" | $PYTHON_CMD -c "import sys,json; print(json.dumps(json.loads(sys.stdin.read()), indent=2))" > "$ALERTS_FILE.tmp"
        mv "$ALERTS_FILE.tmp" "$ALERTS_FILE"
    elif [ ! -f "$ALERTS_FILE" ]; then
        echo "[]" > "$ALERTS_FILE"
    fi
}

# Main loop
load_config

if [ "$ONCE" = true ]; then
    echo ""
    echo "Running single drift check..."
    check_drift
    echo ""
    echo "Check complete."
else
    echo ""
    echo "Starting continuous monitoring (Ctrl+C to stop)..."
    echo "Check interval: 60 seconds"
    echo ""

    while true; do
        check_drift
        sleep 60
    done
fi
