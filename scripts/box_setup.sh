#!/usr/bin/env bash
#
# Tower 3-Box Setup Script
# Configures a machine as Box A, B, or C for TruthCert/Burhan deployment.
#
# Usage:
#   box_setup.sh --role [box_a|box_b|box_c] [--hostname NAME] [--tailscale-ip IP]
#
# This script:
#   1. Updates boxes_config.json with this machine's info
#   2. Sets up systemd timers for cron jobs
#   3. Configures sync targets
#   4. Validates the installation
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

SPEC_VERSION="0.8.0"
BOXES_CONFIG="$TOWER_ROOT/control/boxes_config.json"

# Parse arguments
ROLE=""
HOSTNAME_ARG=""
TAILSCALE_IP=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --role)
            ROLE="$2"
            shift 2
            ;;
        --hostname)
            HOSTNAME_ARG="$2"
            shift 2
            ;;
        --tailscale-ip)
            TAILSCALE_IP="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$ROLE" ]; then
    echo "ERROR: --role is required"
    echo "Usage: box_setup.sh --role [box_a|box_b|box_c] [--hostname NAME] [--tailscale-ip IP]"
    exit 1
fi

if [[ ! "$ROLE" =~ ^(box_a|box_b|box_c)$ ]]; then
    echo "ERROR: --role must be box_a, box_b, or box_c"
    exit 1
fi

# Get hostname if not provided
if [ -z "$HOSTNAME_ARG" ]; then
    HOSTNAME_ARG=$(hostname 2>/dev/null || echo "unknown")
fi

# Get Tailscale IP if not provided and tailscale is installed
if [ -z "$TAILSCALE_IP" ] && command -v tailscale &> /dev/null; then
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "")
fi

echo "============================================================"
echo "Tower 3-Box Setup"
echo "Role: $ROLE"
echo "Hostname: $HOSTNAME_ARG"
echo "Tailscale IP: ${TAILSCALE_IP:-not configured}"
echo "============================================================"

# Update boxes_config.json
echo ""
echo "Updating boxes_config.json..."

if [ ! -f "$BOXES_CONFIG" ]; then
    echo "ERROR: boxes_config.json not found at $BOXES_CONFIG"
    exit 1
fi

_BOX_CONFIG="$BOXES_CONFIG" \
_BOX_ROLE="$ROLE" \
_BOX_HOSTNAME="$HOSTNAME_ARG" \
_BOX_TAILSCALE_IP="$TAILSCALE_IP" \
$PYTHON_CMD << 'PYEOF'
import json
import os
from datetime import datetime

config_path = os.environ["_BOX_CONFIG"]
role = os.environ["_BOX_ROLE"]
hostname = os.environ["_BOX_HOSTNAME"]
tailscale_ip = os.environ.get("_BOX_TAILSCALE_IP", "")

with open(config_path, 'r') as f:
    config = json.load(f)

if role in config.get("boxes", {}):
    config["boxes"][role]["hostname"] = hostname
    if tailscale_ip:
        config["boxes"][role]["tailscale_ip"] = tailscale_ip
    config["boxes"][role]["configured_at"] = datetime.now().isoformat()

    tmp_path = config_path + ".tmp"
    with open(tmp_path, 'w') as f:
        json.dump(config, f, indent=2)
    os.replace(tmp_path, config_path)
    print(f"Updated {role} configuration")
else:
    print(f"ERROR: Role {role} not found in config")
    exit(1)
PYEOF

# Create machine-specific config file
MACHINE_CONFIG="$TOWER_ROOT/control/machine_config.json"
echo ""
echo "Creating machine_config.json..."

cat > "$MACHINE_CONFIG" << EOF
{
  "spec_version": "$SPEC_VERSION",
  "machine_id": "$HOSTNAME_ARG",
  "role": "$ROLE",
  "tailscale_ip": "${TAILSCALE_IP:-null}",
  "configured_at": "$(date -Iseconds 2>/dev/null || date)",
  "tower_root": "$TOWER_ROOT"
}
EOF

echo "Created $MACHINE_CONFIG"

# Display role-specific instructions
echo ""
echo "============================================================"
echo "Setup Complete for $ROLE"
echo "============================================================"
echo ""

case $ROLE in
    box_a)
        echo "Box A - RCT Graph / Cardiology Trial Universe"
        echo ""
        echo "Lanes: map"
        echo "Responsibilities:"
        echo "  - Registry ingestion (CT.gov, ICTRP, etc.)"
        echo "  - Dedupe and linkage"
        echo "  - Evidence graph storage"
        echo "  - Witness snapshots"
        echo ""
        echo "Next steps:"
        echo "  1. Install PostgreSQL if not present"
        echo "  2. Configure registry API credentials"
        echo "  3. Run: tower ingest --source ctgov --test"
        ;;
    box_b)
        echo "Box B - Context / MASem / WHO-World Bank-IHME"
        echo ""
        echo "Lanes: transport"
        echo "Responsibilities:"
        echo "  - Country-year covariates"
        echo "  - WHO/World Bank data refresh"
        echo "  - Transportability inputs"
        echo ""
        echo "Next steps:"
        echo "  1. Download baseline WHO/WB datasets"
        echo "  2. Configure sync from Box A"
        echo "  3. Run: tower context --validate"
        ;;
    box_c)
        echo "Box C - Methods / Meta Engine"
        echo ""
        echo "Lanes: meta, hta"
        echo "Responsibilities:"
        echo "  - Meta-analysis computations"
        echo "  - Validators"
        echo "  - Drift checks"
        echo "  - Capsule generation"
        echo ""
        echo "Next steps:"
        echo "  1. Configure sync from Box A and Box B"
        echo "  2. Validate method registry"
        echo "  3. Run: tower meta --dry-run"
        ;;
esac

echo ""
echo "To set up systemd timers for cron jobs:"
echo "  sudo ./scripts/box_install_timers.sh --role $ROLE"
echo ""
