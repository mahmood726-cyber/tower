#!/usr/bin/env bash
#
# Generate SHA256 manifest for proofpack
#
# Usage:
#   bash tower/addons/signing/proofpack_hash.sh --proofpack <dir>
#

set -euo pipefail

usage() {
    echo "Usage: $0 --proofpack <dir>"
    echo ""
    echo "Options:"
    echo "  --proofpack <dir>   Path to proofpack directory"
    exit 1
}

PROOFPACK_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --proofpack)
            PROOFPACK_DIR="$2"
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

if [[ -z "$PROOFPACK_DIR" ]]; then
    echo "ERROR: --proofpack is required"
    usage
fi

if [[ ! -d "$PROOFPACK_DIR" ]]; then
    echo "ERROR: Proofpack directory not found: $PROOFPACK_DIR"
    exit 1
fi

cd "$PROOFPACK_DIR"

echo "Generating SHA256 manifest for: $PROOFPACK_DIR"

# Generate manifest with deterministic order
# Exclude the manifest itself and any signatures
find . -type f \
    ! -name "manifest.sha256" \
    ! -name "manifest.sha256.asc" \
    ! -name "signature.json" \
    -print0 | \
    sort -z | \
    xargs -0 sha256sum > manifest.sha256.tmp

mv manifest.sha256.tmp manifest.sha256

FILE_COUNT=$(wc -l < manifest.sha256)
echo "Created manifest.sha256 with $FILE_COUNT file(s)"

# Print manifest hash
MANIFEST_HASH=$(sha256sum manifest.sha256 | cut -d' ' -f1)
echo "Manifest SHA256: $MANIFEST_HASH"
