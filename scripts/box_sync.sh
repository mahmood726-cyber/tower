#!/usr/bin/env bash
#
# Tower 3-Box Sync Script
# Synchronizes data between boxes using rsync over SSH/Tailscale.
#
# Usage:
#   box_sync.sh --from [box_a|box_b|box_c] --to [box_a|box_b|box_c] [--dry-run]
#   box_sync.sh --pull-from [box_a|box_b|box_c] [--dry-run]
#   box_sync.sh --push-to [box_a|box_b|box_c] [--dry-run]
#
# Syncs:
#   - control/status.json
#   - control/drift_ledger.json
#   - GRAPH/ (evidence graph data)
#   - VIEWS/ (query views)
#   - capsules/ (proof bundles)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$SCRIPT_DIR")"

# Detect Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Neither python3 nor python found"
    exit 1
fi

BOXES_CONFIG="$TOWER_ROOT/control/boxes_config.json"
MACHINE_CONFIG="$TOWER_ROOT/control/machine_config.json"

# Parse arguments
FROM_BOX=""
TO_BOX=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --from)
            FROM_BOX="$2"
            shift 2
            ;;
        --to)
            TO_BOX="$2"
            shift 2
            ;;
        --pull-from)
            FROM_BOX="$2"
            TO_BOX="local"
            shift 2
            ;;
        --push-to)
            FROM_BOX="local"
            TO_BOX="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$FROM_BOX" ] || [ -z "$TO_BOX" ]; then
    echo "ERROR: --from and --to are required (or use --pull-from / --push-to)"
    echo "Usage: box_sync.sh --from box_a --to box_c [--dry-run]"
    exit 1
fi

# Get box connection info
get_box_connection() {
    local box="$1"
    if [ "$box" = "local" ]; then
        echo "local"
        return
    fi

    _BOX_CONFIG="$BOXES_CONFIG" \
    _BOX_NAME="$box" \
    $PYTHON_CMD -c "
import json
import os

config_path = os.environ['_BOX_CONFIG']
box = os.environ['_BOX_NAME']

with open(config_path) as f:
    config = json.load(f)

box_cfg = config.get('boxes', {}).get(box, {})
ip = box_cfg.get('tailscale_ip') or box_cfg.get('hostname')
user = box_cfg.get('ssh_user', 'tower')

if ip:
    print(f'{user}@{ip}')
else:
    print('UNCONFIGURED')
" 2>/dev/null
}

FROM_CONN=$(get_box_connection "$FROM_BOX")
TO_CONN=$(get_box_connection "$TO_BOX")

if [ "$FROM_CONN" = "UNCONFIGURED" ] && [ "$FROM_BOX" != "local" ]; then
    echo "ERROR: $FROM_BOX is not configured in boxes_config.json"
    exit 1
fi

if [ "$TO_CONN" = "UNCONFIGURED" ] && [ "$TO_BOX" != "local" ]; then
    echo "ERROR: $TO_BOX is not configured in boxes_config.json"
    exit 1
fi

echo "============================================================"
echo "Tower Box Sync"
echo "From: $FROM_BOX ($FROM_CONN)"
echo "To: $TO_BOX ($TO_CONN)"
echo "Mode: $([ "$DRY_RUN" = true ] && echo 'DRY RUN' || echo 'EXECUTE')"
echo "============================================================"

# Build rsync options
RSYNC_OPTS="-avz --progress"
if [ "$DRY_RUN" = true ]; then
    RSYNC_OPTS="$RSYNC_OPTS --dry-run"
fi

# Exclusions
RSYNC_OPTS="$RSYNC_OPTS --exclude='*.tmp' --exclude='*.log' --exclude='__pycache__/' --exclude='.git/'"

# Paths to sync
SYNC_PATHS=(
    "control/status.json"
    "control/drift_ledger.json"
    "control/boxes_config.json"
    "GRAPH/"
    "VIEWS/"
    "capsules/"
)

# Perform sync
echo ""
echo "Syncing paths..."

for path in "${SYNC_PATHS[@]}"; do
    echo ""
    echo "--- Syncing: $path ---"

    if [ "$FROM_BOX" = "local" ]; then
        # Push to remote
        SRC="$TOWER_ROOT/$path"
        DST="$TO_CONN:$TOWER_ROOT/$path"
    elif [ "$TO_BOX" = "local" ]; then
        # Pull from remote
        SRC="$FROM_CONN:$TOWER_ROOT/$path"
        DST="$TOWER_ROOT/$path"
    else
        # Remote to remote (via local)
        echo "  Remote-to-remote sync not yet supported"
        continue
    fi

    # Check if source exists (for local sources)
    if [ "$FROM_BOX" = "local" ]; then
        if [ ! -e "$TOWER_ROOT/$path" ]; then
            echo "  Source does not exist: $path (skipping)"
            continue
        fi
    fi

    # Create destination directory if needed
    if [ "$TO_BOX" = "local" ]; then
        dest_dir=$(dirname "$TOWER_ROOT/$path")
        mkdir -p "$dest_dir"
    fi

    # Run rsync
    if rsync $RSYNC_OPTS "$SRC" "$DST" 2>/dev/null; then
        echo "  OK"
    else
        echo "  FAILED (may not exist on source)"
    fi
done

echo ""
echo "============================================================"
echo "Sync complete"
echo "============================================================"
