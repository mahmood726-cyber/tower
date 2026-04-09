#!/usr/bin/env bash
#
# Build and sign a proofpack for a card
#
# Usage:
#   bash tower/addons/signing/tower_proofpack_signed.sh --card CARD-001
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

usage() {
    echo "Usage: $0 --card <CARD_ID>"
    echo ""
    echo "Options:"
    echo "  --card <CARD_ID>    Card ID to build proofpack for"
    exit 1
}

CARD_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --card)
            CARD_ID="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if [[ -z "$CARD_ID" ]]; then
    echo "ERROR: --card is required"
    usage
fi

echo "============================================================"
echo "Tower Signed Proofpack"
echo "Card: $CARD_ID"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"
echo ""

# Step 1: Build proofpack using existing script
PROOFPACK_SCRIPT="$TOWER_ROOT/scripts/tower_proofpack.sh"

if [[ ! -f "$PROOFPACK_SCRIPT" ]]; then
    echo "ERROR: tower_proofpack.sh not found at: $PROOFPACK_SCRIPT"
    exit 1
fi

echo "Step 1: Building proofpack..."
bash "$PROOFPACK_SCRIPT" --card "$CARD_ID" || {
    echo "WARNING: Proofpack build failed or no proofpack created"
}

# Step 2: Find the newest proofpack for this card
echo ""
echo "Step 2: Finding proofpack..."

PROOFPACK_DIR=""
TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d 2>/dev/null || echo "")

# Search in today and yesterday's directories
for DATE_DIR in "$TODAY" "$YESTERDAY"; do
    if [[ -z "$DATE_DIR" ]]; then
        continue
    fi

    SEARCH_DIR="$TOWER_ROOT/proofpacks/$DATE_DIR/$CARD_ID"
    if [[ -d "$SEARCH_DIR" ]]; then
        PROOFPACK_DIR="$SEARCH_DIR"
        break
    fi
done

# If not found, search all dates
if [[ -z "$PROOFPACK_DIR" || ! -d "$PROOFPACK_DIR" ]]; then
    PROOFPACK_DIR=$(find "$TOWER_ROOT/proofpacks" -type d -name "$CARD_ID" 2>/dev/null | head -n 1 || echo "")
fi

if [[ -z "$PROOFPACK_DIR" || ! -d "$PROOFPACK_DIR" ]]; then
    echo "ERROR: No proofpack found for $CARD_ID"
    echo "Searched in: $TOWER_ROOT/proofpacks/"
    exit 1
fi

echo "Found: $PROOFPACK_DIR"

# Step 3: Generate hash manifest
echo ""
echo "Step 3: Generating hash manifest..."
bash "$SCRIPT_DIR/proofpack_hash.sh" --proofpack "$PROOFPACK_DIR"

# Step 4: Sign the manifest
echo ""
echo "Step 4: Signing proofpack..."
bash "$SCRIPT_DIR/proofpack_sign.sh" --proofpack "$PROOFPACK_DIR"

# Step 5: Verify
echo ""
echo "Step 5: Verifying..."
bash "$SCRIPT_DIR/proofpack_verify.sh" --proofpack "$PROOFPACK_DIR"

echo ""
echo "============================================================"
echo "Signed proofpack created successfully"
echo "Location: $PROOFPACK_DIR"
echo "============================================================"
