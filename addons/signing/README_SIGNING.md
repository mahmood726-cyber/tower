# Tower Signed Proofpacks Addon

Tamper-evident signing and transparency logging for Tower proofpacks.

## Overview

This addon provides:
- **SHA256 hashing**: Creates manifest of all files in proofpack
- **Optional GPG signing**: Signs manifest if GPG key available
- **Transparency log**: Append-only hash chain for audit trail

## Requirements

- `sha256sum` (coreutils)
- `openssl` or `gpg` (optional, for signing)

## Usage

### Generate Manifest Hash

```bash
bash tower/addons/signing/proofpack_hash.sh --proofpack tower/proofpacks/2026-01-17/CARD-001/
```

Creates `manifest.sha256` with SHA256 hashes of all files.

### Sign Proofpack

```bash
bash tower/addons/signing/proofpack_sign.sh --proofpack tower/proofpacks/2026-01-17/CARD-001/
```

Creates:
- `signature.json` with signing metadata
- `manifest.sha256.asc` (if GPG available)

### Verify Proofpack

```bash
bash tower/addons/signing/proofpack_verify.sh --proofpack tower/proofpacks/2026-01-17/CARD-001/
```

Verifies:
- All file hashes match manifest
- GPG signature (if present)

### Full Workflow: Sign a Card

```bash
bash tower/addons/signing/tower_proofpack_signed.sh --card CARD-001
```

This:
1. Calls `tower/scripts/tower_proofpack.sh --card CARD-001`
2. Finds the newest proofpack for that card
3. Generates hash manifest
4. Signs the manifest
5. Appends to transparency log

## Transparency Log

The transparency log creates an audit trail of all signed proofpacks.

### Files

- `tower/proofpacks/transparency.log` - Simple CSV log
- `tower/proofpacks/transparency_chain.log` - Hash-chained log

### Chain Format

Each line includes:
- `timestamp`
- `proofpack_path`
- `manifest_sha256`
- `prev_line_sha256` (for chain integrity)
- `this_line_sha256`

### Verify Chain

```bash
bash tower/addons/signing/transparency_verify.sh
```

## Signing Modes

### 1. GPG Signing (Preferred)

If GPG is available with a secret key:

```bash
# List available keys
gpg --list-secret-keys

# Sign (will prompt for passphrase if needed)
bash tower/addons/signing/proofpack_sign.sh --proofpack <dir>
```

### 2. SHA256-Only (Fallback)

If GPG not available, creates unsigned but hashed manifest:

```json
{
  "method": "sha256-only",
  "unsigned_but_hashed": true,
  "created_at": "2026-01-17T10:30:00Z"
}
```

## Output Files

### manifest.sha256

```
a1b2c3d4...  ./run_context.json
e5f6g7h8...  ./run_summary.json
...
```

### signature.json

```json
{
  "spec_version": "v1.5.5",
  "method": "gpg",
  "manifest_sha256": "abc123...",
  "key_fingerprint": "ABCD1234...",
  "created_at": "2026-01-17T10:30:00Z",
  "signer_id": "user@hostname"
}
```

### transparency_chain.log

```
2026-01-17T10:30:00Z|tower/proofpacks/2026-01-17/CARD-001|abc123...|null|def456...
2026-01-17T10:31:00Z|tower/proofpacks/2026-01-17/CARD-002|ghi789...|def456...|jkl012...
```

## Key Generation (Optional)

If you need to generate a new signing key:

```bash
# Generate GPG key
gpg --gen-key

# Or use OpenSSL for simple signing
openssl genpkey -algorithm ed25519 -out tower/addons/signing/private.pem
openssl pkey -in tower/addons/signing/private.pem -pubout -out tower/addons/signing/public.pem
```

## Troubleshooting

**"gpg not found"**: Install GPG or use SHA256-only mode.

**"no secret key"**: Generate a GPG key or use SHA256-only mode.

**"manifest mismatch"**: Files changed after signing. Re-sign the proofpack.

**"chain broken"**: Transparency log was tampered with. Investigate immediately.
