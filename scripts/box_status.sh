#!/usr/bin/env bash
#
# Tower 3-Box Status Script
# Shows status of all boxes in the cluster.
#
# Usage:
#   box_status.sh [--check-connectivity]
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
CHECK_CONNECTIVITY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --check-connectivity)
            CHECK_CONNECTIVITY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "============================================================"
echo "Tower 3-Box Cluster Status"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"

# Show current machine role
if [ -f "$MACHINE_CONFIG" ]; then
    echo ""
    echo "This Machine:"
    $PYTHON_CMD -c "
import json
with open('$MACHINE_CONFIG') as f:
    cfg = json.load(f)
print(f\"  Role: {cfg.get('role', 'unknown')}\" )
print(f\"  Machine ID: {cfg.get('machine_id', 'unknown')}\")
print(f\"  Tailscale: {cfg.get('tailscale_ip', 'not configured')}\")
"
else
    echo ""
    echo "This Machine: NOT CONFIGURED"
    echo "  Run: ./scripts/box_setup.sh --role [box_a|box_b|box_c]"
fi

# Show all boxes
echo ""
echo "Cluster Configuration:"
echo "----------------------"

if [ ! -f "$BOXES_CONFIG" ]; then
    echo "ERROR: boxes_config.json not found"
    exit 1
fi

$PYTHON_CMD << 'PYEOF'
import json
import os

config_path = os.environ.get("BOXES_CONFIG", "control/boxes_config.json")
check_conn = os.environ.get("CHECK_CONNECTIVITY", "false") == "true"

try:
    with open(config_path) as f:
        config = json.load(f)
except FileNotFoundError:
    config_path = "control/boxes_config.json"
    with open(config_path) as f:
        config = json.load(f)

boxes = config.get("boxes", {})

for box_id, box_cfg in boxes.items():
    print(f"\n{box_id.upper()}: {box_cfg.get('name', 'Unknown')}")
    print(f"  Role: {box_cfg.get('role', 'unknown')}")
    print(f"  Lanes: {', '.join(box_cfg.get('lanes', []))}")

    hostname = box_cfg.get('hostname')
    tailscale = box_cfg.get('tailscale_ip')

    if hostname:
        print(f"  Hostname: {hostname}")
    else:
        print(f"  Hostname: NOT CONFIGURED")

    if tailscale:
        print(f"  Tailscale: {tailscale}")

    configured_at = box_cfg.get('configured_at')
    if configured_at:
        print(f"  Configured: {configured_at}")

    # Show responsibilities
    responsibilities = box_cfg.get('responsibilities', [])
    if responsibilities:
        print(f"  Tasks: {len(responsibilities)}")
        for r in responsibilities[:3]:
            print(f"    - {r}")
        if len(responsibilities) > 3:
            print(f"    ... and {len(responsibilities) - 3} more")
PYEOF

# Check connectivity if requested
if [ "$CHECK_CONNECTIVITY" = true ]; then
    echo ""
    echo "Connectivity Check:"
    echo "-------------------"

    for box in box_a box_b box_c; do
        ip=$($PYTHON_CMD -c "
import json
with open('$BOXES_CONFIG') as f:
    cfg = json.load(f)
box = cfg.get('boxes', {}).get('$box', {})
print(box.get('tailscale_ip') or box.get('hostname') or '')
" 2>/dev/null)

        if [ -n "$ip" ]; then
            if ping -c 1 -W 2 "$ip" &> /dev/null; then
                echo "  $box ($ip): REACHABLE"
            else
                echo "  $box ($ip): UNREACHABLE"
            fi
        else
            echo "  $box: NOT CONFIGURED"
        fi
    done
fi

echo ""
echo "============================================================"
echo "Sync Protocol:"
$PYTHON_CMD -c "
import json
with open('$BOXES_CONFIG') as f:
    cfg = json.load(f)
sync = cfg.get('sync_protocol', {})
print(f\"  Method: {sync.get('method', 'unknown')}\")
print(f\"  Frequency: every {sync.get('frequency_minutes', '?')} minutes\")
print(f\"  Paths: {len(sync.get('paths_to_sync', []))} configured\")
"
echo "============================================================"
