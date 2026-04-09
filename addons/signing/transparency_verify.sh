#!/usr/bin/env bash
#
# Verify transparency log chain integrity
#
# Usage:
#   bash tower/addons/signing/transparency_verify.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
PROOFPACKS_DIR="$TOWER_ROOT/proofpacks"

CHAIN_LOG="$PROOFPACKS_DIR/transparency_chain.log"

if [[ ! -f "$CHAIN_LOG" ]]; then
    echo "No transparency chain log found: $CHAIN_LOG"
    exit 0
fi

echo "Verifying transparency chain: $CHAIN_LOG"
echo ""

LINE_NUM=0
PREV_HASH="null"
ERRORS=0

while IFS= read -r line; do
    LINE_NUM=$((LINE_NUM + 1))

    # Skip empty lines
    if [[ -z "$line" ]]; then
        continue
    fi

    # Parse line: timestamp|path|manifest_sha256|prev_hash|this_hash
    IFS='|' read -ra PARTS <<< "$line"

    if [[ ${#PARTS[@]} -lt 5 ]]; then
        echo "Line $LINE_NUM: [FAIL] Invalid format"
        ERRORS=$((ERRORS + 1))
        continue
    fi

    TIMESTAMP="${PARTS[0]}"
    PATH_VAL="${PARTS[1]}"
    MANIFEST="${PARTS[2]}"
    RECORDED_PREV="${PARTS[3]}"
    RECORDED_THIS="${PARTS[4]}"

    # Verify previous hash matches
    if [[ "$RECORDED_PREV" != "$PREV_HASH" ]]; then
        echo "Line $LINE_NUM: [FAIL] Chain broken!"
        echo "  Expected prev: $PREV_HASH"
        echo "  Recorded prev: $RECORDED_PREV"
        ERRORS=$((ERRORS + 1))
    fi

    # Verify this line's hash
    LINE_BASE="$TIMESTAMP|$PATH_VAL|$MANIFEST|$RECORDED_PREV"
    CALCULATED_HASH=$(echo -n "$LINE_BASE" | sha256sum | cut -d' ' -f1)

    if [[ "$CALCULATED_HASH" != "$RECORDED_THIS" ]]; then
        echo "Line $LINE_NUM: [FAIL] Hash mismatch!"
        echo "  Calculated: $CALCULATED_HASH"
        echo "  Recorded:   $RECORDED_THIS"
        ERRORS=$((ERRORS + 1))
    else
        echo "Line $LINE_NUM: [OK] $PATH_VAL"
    fi

    # Update prev for next iteration
    PREV_HASH="$RECORDED_THIS"

done < "$CHAIN_LOG"

echo ""
echo "Verified $LINE_NUM entries"

if [[ $ERRORS -eq 0 ]]; then
    echo "CHAIN VERIFICATION PASSED"
    exit 0
else
    echo "CHAIN VERIFICATION FAILED ($ERRORS error(s))"
    exit 1
fi
