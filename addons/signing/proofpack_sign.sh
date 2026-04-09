#!/usr/bin/env bash
#
# Sign proofpack manifest
#
# Usage:
#   bash tower/addons/signing/proofpack_sign.sh --proofpack <dir>
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

MANIFEST_FILE="$PROOFPACK_DIR/manifest.sha256"
SIGNATURE_FILE="$PROOFPACK_DIR/signature.json"

# Generate manifest if not exists
if [[ ! -f "$MANIFEST_FILE" ]]; then
    echo "Generating manifest first..."
    bash "$SCRIPT_DIR/proofpack_hash.sh" --proofpack "$PROOFPACK_DIR"
fi

# Get manifest hash
MANIFEST_SHA256=$(sha256sum "$MANIFEST_FILE" | cut -d' ' -f1)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SIGNER_ID="${USER:-unknown}@${HOSTNAME:-unknown}"

echo "Signing proofpack: $PROOFPACK_DIR"
echo "Manifest SHA256: $MANIFEST_SHA256"

# Try GPG signing
GPG_AVAILABLE=false
GPG_FINGERPRINT=""

if command -v gpg &> /dev/null; then
    # Check if there's a secret key
    if gpg --list-secret-keys 2>/dev/null | grep -q "sec"; then
        GPG_AVAILABLE=true
        # Get first key fingerprint
        GPG_FINGERPRINT=$(gpg --list-secret-keys --with-colons 2>/dev/null | grep "^fpr" | head -n1 | cut -d: -f10 || echo "")
    fi
fi

if [[ "$GPG_AVAILABLE" == "true" ]]; then
    echo "Using GPG signing"

    # Create detached signature
    gpg --armor --detach-sign --output "$PROOFPACK_DIR/manifest.sha256.asc" "$MANIFEST_FILE" 2>/dev/null || {
        echo "WARNING: GPG signing failed, falling back to SHA256-only"
        GPG_AVAILABLE=false
    }
fi

if [[ "$GPG_AVAILABLE" == "true" ]]; then
    # Write signature.json with GPG
    cat > "$SIGNATURE_FILE.tmp" << EOF
{
  "spec_version": "v1.5.5",
  "method": "gpg",
  "manifest_sha256": "$MANIFEST_SHA256",
  "key_fingerprint": "$GPG_FINGERPRINT",
  "created_at": "$TIMESTAMP",
  "signer_id": "$SIGNER_ID",
  "unsigned_but_hashed": false
}
EOF
    echo "Created GPG signature: manifest.sha256.asc"
else
    # Write signature.json without GPG
    cat > "$SIGNATURE_FILE.tmp" << EOF
{
  "spec_version": "v1.5.5",
  "method": "sha256-only",
  "manifest_sha256": "$MANIFEST_SHA256",
  "key_fingerprint": null,
  "created_at": "$TIMESTAMP",
  "signer_id": "$SIGNER_ID",
  "unsigned_but_hashed": true
}
EOF
    echo "Created SHA256-only signature (GPG not available)"
fi

mv "$SIGNATURE_FILE.tmp" "$SIGNATURE_FILE"
echo "Created: $SIGNATURE_FILE"

# Append to transparency log
bash "$SCRIPT_DIR/transparency_append.sh" --proofpack "$PROOFPACK_DIR" || true
