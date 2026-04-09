#!/usr/bin/env bash
#
# Verify proofpack integrity
#
# Usage:
#   bash tower/addons/signing/proofpack_verify.sh --proofpack <dir>
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

MANIFEST_FILE="$PROOFPACK_DIR/manifest.sha256"
SIGNATURE_FILE="$PROOFPACK_DIR/signature.json"
GPG_SIG_FILE="$PROOFPACK_DIR/manifest.sha256.asc"

echo "Verifying proofpack: $PROOFPACK_DIR"
echo ""

ERRORS=0

# Check manifest exists
if [[ ! -f "$MANIFEST_FILE" ]]; then
    echo "ERROR: Manifest not found: $MANIFEST_FILE"
    exit 1
fi

# Verify file hashes
echo "Verifying file hashes..."
cd "$PROOFPACK_DIR"

if sha256sum --check --quiet manifest.sha256 2>/dev/null; then
    echo "  [OK] All file hashes match"
else
    echo "  [FAIL] Hash mismatch detected!"
    sha256sum --check manifest.sha256 2>&1 | grep -v ": OK$" || true
    ERRORS=$((ERRORS + 1))
fi

cd - > /dev/null

# Check signature.json
if [[ -f "$SIGNATURE_FILE" ]]; then
    echo ""
    echo "Checking signature.json..."

    # Extract method
    if command -v jq &> /dev/null; then
        METHOD=$(jq -r '.method // "unknown"' "$SIGNATURE_FILE")
        MANIFEST_SHA256=$(jq -r '.manifest_sha256 // "unknown"' "$SIGNATURE_FILE")
        UNSIGNED=$(jq -r '.unsigned_but_hashed // false' "$SIGNATURE_FILE")
    else
        METHOD=$(grep -o '"method"[[:space:]]*:[[:space:]]*"[^"]*"' "$SIGNATURE_FILE" | cut -d'"' -f4 || echo "unknown")
        MANIFEST_SHA256=$(grep -o '"manifest_sha256"[[:space:]]*:[[:space:]]*"[^"]*"' "$SIGNATURE_FILE" | cut -d'"' -f4 || echo "unknown")
        UNSIGNED="unknown"
    fi

    echo "  Method: $METHOD"

    # Verify manifest hash matches signature
    ACTUAL_HASH=$(sha256sum "$MANIFEST_FILE" | cut -d' ' -f1)
    if [[ "$ACTUAL_HASH" == "$MANIFEST_SHA256" ]]; then
        echo "  [OK] Manifest hash matches signature"
    else
        echo "  [FAIL] Manifest hash mismatch!"
        echo "    Expected: $MANIFEST_SHA256"
        echo "    Actual:   $ACTUAL_HASH"
        ERRORS=$((ERRORS + 1))
    fi

    # Verify GPG signature if present
    if [[ -f "$GPG_SIG_FILE" ]]; then
        echo ""
        echo "Verifying GPG signature..."
        if command -v gpg &> /dev/null; then
            if gpg --verify "$GPG_SIG_FILE" "$MANIFEST_FILE" 2>/dev/null; then
                echo "  [OK] GPG signature valid"
            else
                echo "  [FAIL] GPG signature invalid!"
                ERRORS=$((ERRORS + 1))
            fi
        else
            echo "  [WARN] GPG not available, cannot verify signature"
        fi
    elif [[ "$UNSIGNED" == "true" ]]; then
        echo "  [INFO] SHA256-only mode (no GPG signature)"
    fi
else
    echo ""
    echo "[WARN] No signature.json found"
fi

echo ""
if [[ $ERRORS -eq 0 ]]; then
    echo "VERIFICATION PASSED"
    exit 0
else
    echo "VERIFICATION FAILED ($ERRORS error(s))"
    exit 1
fi
