#!/usr/bin/env bash
#
# Append proofpack to transparency log (hash chain)
#
# Usage:
#   bash tower/addons/signing/transparency_append.sh --proofpack <dir>
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
PROOFPACKS_DIR="$TOWER_ROOT/proofpacks"

# Ensure proofpacks directory exists
mkdir -p "$PROOFPACKS_DIR"

SIMPLE_LOG="$PROOFPACKS_DIR/transparency.log"
CHAIN_LOG="$PROOFPACKS_DIR/transparency_chain.log"

usage() {
    echo "Usage: $0 --proofpack <dir>"
    exit 1
}

PROOFPACK_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --proofpack)
            PROOFPACK_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if [[ -z "$PROOFPACK_DIR" ]]; then
    echo "ERROR: --proofpack is required"
    usage
fi

MANIFEST_FILE="$PROOFPACK_DIR/manifest.sha256"

if [[ ! -f "$MANIFEST_FILE" ]]; then
    echo "ERROR: Manifest not found: $MANIFEST_FILE"
    exit 1
fi

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
MANIFEST_SHA256=$(sha256sum "$MANIFEST_FILE" | cut -d' ' -f1)

# Make proofpack path relative if possible
if [[ "$PROOFPACK_DIR" == "$TOWER_ROOT"* ]]; then
    RELATIVE_PATH="${PROOFPACK_DIR#$TOWER_ROOT/}"
else
    RELATIVE_PATH="$PROOFPACK_DIR"
fi

# Append to simple log
echo "$TIMESTAMP,$RELATIVE_PATH,$MANIFEST_SHA256" >> "$SIMPLE_LOG"

# Get previous line hash for chain
if [[ -f "$CHAIN_LOG" && -s "$CHAIN_LOG" ]]; then
    PREV_LINE=$(tail -n 1 "$CHAIN_LOG")
    PREV_HASH=$(echo -n "$PREV_LINE" | sha256sum | cut -d' ' -f1)
else
    PREV_HASH="null"
fi

# Build this line (without hash)
THIS_LINE_BASE="$TIMESTAMP|$RELATIVE_PATH|$MANIFEST_SHA256|$PREV_HASH"

# Calculate this line's hash
THIS_HASH=$(echo -n "$THIS_LINE_BASE" | sha256sum | cut -d' ' -f1)

# Append to chain log
echo "$THIS_LINE_BASE|$THIS_HASH" >> "$CHAIN_LOG"

echo "Added to transparency log:"
echo "  Path: $RELATIVE_PATH"
echo "  Manifest: $MANIFEST_SHA256"
echo "  Chain hash: $THIS_HASH"
