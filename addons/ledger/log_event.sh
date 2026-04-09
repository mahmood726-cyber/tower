#!/usr/bin/env bash
# log_event.sh - Bash helper for Tower Event Ledger
# Part of Tower v1.5.5 Ledger Add-on
#
# Usage:
#   bash log_event.sh <event_type> [card_id] [data_json]
#
#   # As a source-able function:
#   source tower/addons/ledger/log_event.sh
#   log_event "card.state_change" "CARD-042" '{"from": "ACTIVE", "to": "GREEN"}'
#
# Examples:
#   log_event.sh "card.created" "CARD-043" '{"title": "New feature"}'
#   log_event.sh "system.backup_created" "" '{"file": "status_backup.json"}'
#   log_event.sh "validation.pass" "CARD-042"

set -euo pipefail

# Find tower root
find_tower_root() {
    local dir="${1:-$(pwd)}"
    while [[ "$dir" != "/" ]]; do
        if [[ -d "$dir/tower/control" ]]; then
            echo "$dir/tower"
            return 0
        fi
        if [[ -d "$dir/control" && -f "$dir/control/status.json" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    # Fallback
    echo "tower"
}

TOWER_ROOT="${TOWER_ROOT:-$(find_tower_root)}"
LEDGER_FILE="${LEDGER_FILE:-$TOWER_ROOT/control/event_ledger.jsonl}"
LOCK_FILE="${LEDGER_FILE}.lock"

# Ensure control directory exists
mkdir -p "$(dirname "$LEDGER_FILE")"

# Generate event ID
generate_event_id() {
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local random_hex
    random_hex=$(head -c 4 /dev/urandom | xxd -p 2>/dev/null || echo "$(date +%N | cut -c1-8)")
    echo "evt_${timestamp}_${random_hex}"
}

# Compute SHA256 hash
compute_hash() {
    local input="$1"
    echo -n "$input" | sha256sum | cut -d' ' -f1
}

# Get last hash from ledger
get_last_hash() {
    if [[ -f "$LEDGER_FILE" ]]; then
        tail -1 "$LEDGER_FILE" 2>/dev/null | jq -r '.hash // empty' 2>/dev/null || echo ""
    else
        echo ""
    fi
}

# Log an event
log_event() {
    local event_type="${1:-}"
    local card_id="${2:-}"
    local data_json="${3:-}"
    local actor="${TOWER_ACTOR:-$(basename "${BASH_SOURCE[1]:-$0}")}"

    if [[ -z "$event_type" ]]; then
        echo "Usage: log_event <event_type> [card_id] [data_json]" >&2
        return 1
    fi

    # Acquire lock (simple flock-based)
    exec 200>"$LOCK_FILE"
    flock -w 30 200 || {
        echo "Error: Could not acquire lock on $LOCK_FILE" >&2
        return 1
    }

    # Generate event
    local event_id
    event_id=$(generate_event_id)

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S.%6NZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Get previous hash
    local prev_hash
    prev_hash=$(get_last_hash)

    # Build event JSON
    local event
    event=$(jq -n \
        --arg id "$event_id" \
        --arg ts "$timestamp" \
        --arg type "$event_type" \
        --arg card "$card_id" \
        --arg actor "$actor" \
        --arg prev "$prev_hash" \
        --argjson data "${data_json:-null}" \
        '{
            id: $id,
            timestamp: $ts,
            type: $type
        }
        + (if $card != "" then {card_id: $card} else {} end)
        + (if $actor != "" then {actor: $actor} else {} end)
        + (if $data != null then {data: $data} else {} end)
        + (if $prev != "" then {prev_hash: ("sha256:" + $prev)} else {} end)'
    )

    # Compute hash
    local hash_input
    hash_input=$(echo "$event" | jq -c --sort-keys '.')
    local hash
    hash="sha256:$(compute_hash "$hash_input")"

    # Add hash to event
    event=$(echo "$event" | jq -c --arg hash "$hash" '. + {hash: $hash}')

    # Append to ledger
    echo "$event" >> "$LEDGER_FILE"

    # Release lock
    flock -u 200

    # Output the event
    echo "$event"
}

# If run as script (not sourced), execute with arguments
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 <event_type> [card_id] [data_json]"
        echo ""
        echo "Examples:"
        echo "  $0 \"card.created\" \"CARD-043\" '{\"title\": \"New feature\"}'"
        echo "  $0 \"system.backup_created\" \"\" '{\"file\": \"backup.json\"}'"
        echo "  $0 \"validation.pass\" \"CARD-042\""
        exit 1
    fi
    log_event "$@"
fi
