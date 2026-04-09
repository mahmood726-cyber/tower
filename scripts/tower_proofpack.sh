#!/usr/bin/env bash
#
# Tower Proofpack Generator
# Assembles a proofpack for a card with manifest and optional zip.
#
# Usage:
#   tower_proofpack.sh --card CARD-XXX [--no-zip]
#
# Creates:
#   tower/proofpacks/YYYY-MM-DD/CARD-XXX/
#     - manifest.json (schema-valid)
#     - artifacts/ (copied evidence)
#     - proofpack.zip (unless --no-zip)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$SCRIPT_DIR")"

# Detect Python command (python3 or python)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Neither python3 nor python found"
    exit 1
fi

# Convert Git Bash path to Windows path for Python (using forward slashes)
to_win_path() {
    local path="$1"
    # Git Bash: /c/Users/... -> C:/Users/...
    if [[ "$path" == /[a-zA-Z]/* ]]; then
        echo "${path:1:1}:${path:2}"
    # Cygwin: /cygdrive/c/Users/... -> C:/Users/...
    elif [[ "$path" == /cygdrive/[a-zA-Z]/* ]]; then
        echo "${path:10:1}:${path:11}"
    else
        echo "$path"
    fi
}

SPEC_VERSION="v1.5.7"

STATUS_FILE="$TOWER_ROOT/control/status.json"
STATUS_FILE_WIN=$(to_win_path "$STATUS_FILE")

# Parse arguments
CARD_ID=""
NO_ZIP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --card)
            CARD_ID="$2"
            shift 2
            ;;
        --no-zip)
            NO_ZIP=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$CARD_ID" ]; then
    echo "ERROR: --card is required"
    echo "Usage: tower_proofpack.sh --card CARD-XXX [--no-zip]"
    exit 1
fi

# Validate CARD_ID format (prevent path traversal / injection)
if ! echo "$CARD_ID" | grep -qE '^CARD-[0-9]+$'; then
    echo "ERROR: --card must match CARD-NNN format (got: $CARD_ID)"
    exit 1
fi

DATE_DIR=$(date +%Y-%m-%d)
PROOFPACK_DIR="$TOWER_ROOT/proofpacks/$DATE_DIR/$CARD_ID"
PROOFPACK_DIR_WIN=$(to_win_path "$PROOFPACK_DIR")
ARTIFACTS_SRC="$TOWER_ROOT/artifacts/$DATE_DIR/$CARD_ID"

echo "============================================================"
echo "Tower Proofpack Generator"
echo "Card: $CARD_ID"
echo "Date: $DATE_DIR"
echo "Output: $PROOFPACK_DIR"
echo "============================================================"

# Create proofpack directory
mkdir -p "$PROOFPACK_DIR/artifacts"

# Get git info
GIT_SHA=""
GIT_BRANCH=""
if command -v git &> /dev/null && git rev-parse --git-dir &> /dev/null; then
    GIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
fi

# Collect run_ids and artifacts
RUN_IDS="[]"
ARTIFACTS_LIST="[]"
EVIDENCE_PATHS="[]"

if [ -d "$ARTIFACTS_SRC" ]; then
    echo ""
    echo "Collecting artifacts..."

    # Find all run directories (portable: -printf is GNU-only)
    RUN_IDS=$($PYTHON_CMD -c "
import os, json
base = '$ARTIFACTS_SRC'
runs = [d for d in os.listdir(base) if d.startswith('run_') and os.path.isdir(os.path.join(base, d))]
print(json.dumps(runs))
" 2>/dev/null || echo "[]")

    # Copy artifacts (use -P to not follow symlinks for security)
    if [ -d "$ARTIFACTS_SRC" ] && [ "$(ls -A "$ARTIFACTS_SRC" 2>/dev/null)" ]; then
        cp -rP "$ARTIFACTS_SRC"/* "$PROOFPACK_DIR/artifacts/" 2>/dev/null || true
    else
        echo "  Warning: No artifacts found in $ARTIFACTS_SRC"
    fi

    # Build artifacts list (env var to avoid heredoc injection)
    ARTIFACTS_LIST=$(_GC_BASE="$PROOFPACK_DIR_WIN/artifacts" $PYTHON_CMD << 'PYEOF'
import os
import json
import hashlib

artifacts = []
base = os.environ["_GC_BASE"]

for root, dirs, files in os.walk(base):
    for f in files:
        path = os.path.join(root, f)
        rel_path = os.path.relpath(path, base)
        ext = os.path.splitext(f)[1].lower()
        file_type = {
            '.json': 'json',
            '.log': 'log',
            '.txt': 'text',
            '.md': 'markdown'
        }.get(ext, 'other')

        # Calculate hash
        sha256 = None
        try:
            with open(path, 'rb') as fh:
                sha256 = hashlib.sha256(fh.read()).hexdigest()
        except:
            pass

        artifacts.append({
            "path": rel_path,
            "type": file_type,
            "sha256": sha256
        })

print(json.dumps(artifacts))
PYEOF
)

    # Collect evidence paths (using Python for safety with special characters)
    EVIDENCE_PATHS=$(_TC_ARTIFACTS="$PROOFPACK_DIR_WIN/artifacts" $PYTHON_CMD << 'PYEOF'
import os, json
base = os.environ.get("_TC_ARTIFACTS", "")
paths = []
if base and os.path.exists(base):
    for root, dirs, files in os.walk(base):
        for f in files:
            if f.endswith('.json') or f.endswith('.log'):
                rel_path = os.path.relpath(os.path.join(root, f), base)
                paths.append(rel_path)
                if len(paths) >= 20:
                    break
        if len(paths) >= 20:
            break
print(json.dumps(paths))
PYEOF
) || EVIDENCE_PATHS="[]"

    echo "  Found $(echo "$RUN_IDS" | $PYTHON_CMD -c "import sys,json; print(len(json.loads(sys.stdin.read())))" 2>/dev/null || echo "0") runs"
fi

# Get gates from status
GATES='{"tests": "NOT_RUN", "validators": "NOT_RUN", "proofpack": "NOT_RUN"}'
VALIDATORS='{"overall_status": "NOT_RUN", "report_path": null}'

if [ -f "$STATUS_FILE" ]; then
    # Normalize gates to string format for manifest (handles both dict and string formats)
    GATES=$(_GC_STATUS="$STATUS_FILE_WIN" _GC_CARD="$CARD_ID" $PYTHON_CMD -c "
import json, os
with open(os.environ['_GC_STATUS']) as f:
    data = json.load(f)
cards = data.get('cards', [])
card = next((c for c in cards if c.get('card_id') == os.environ['_GC_CARD']), {}) if isinstance(cards, list) else cards.get(os.environ['_GC_CARD'], {})
gates = card.get('gates', {'tests': 'NOT_RUN', 'validators': 'NOT_RUN', 'proofpack': 'NOT_RUN'})
# Normalize: if gate is dict with 'status' key, extract the status string
normalized = {}
for k, v in gates.items():
    if isinstance(v, dict) and 'status' in v:
        normalized[k] = v['status']
    else:
        normalized[k] = v
print(json.dumps(normalized))
" 2>/dev/null) || GATES='{"tests": "NOT_RUN", "validators": "NOT_RUN", "proofpack": "NOT_RUN"}'
fi

# Check for validator report
VALIDATOR_REPORT=""
for report in "$PROOFPACK_DIR/artifacts"/*/validator_report.json; do
    if [ -f "$report" ]; then
        VALIDATOR_REPORT=$(basename "$(dirname "$report")")/validator_report.json
        report_win=$(to_win_path "$report")
        VALIDATOR_STATUS=$(_TC_REPORT="$report_win" $PYTHON_CMD -c "import json, os; print(json.load(open(os.environ['_TC_REPORT'])).get('overall_status', 'NOT_RUN'))" 2>/dev/null || echo "NOT_RUN")
        VALIDATORS="{\"overall_status\": \"$VALIDATOR_STATUS\", \"report_path\": \"$VALIDATOR_REPORT\"}"
        break
    fi
done

# Create TruthCert-style manifest with witness chain
CREATED_AT=$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)
MANIFEST_FILE="$PROOFPACK_DIR/manifest.json"
MANIFEST_TMP="$MANIFEST_FILE.tmp"

# Get machine ID
MACHINE_ID="${TOWER_MACHINE:-$(hostname 2>/dev/null || echo 'unknown')}"

# Get assurance level from status
ASSURANCE="none"
if [ -f "$STATUS_FILE" ]; then
    ASSURANCE=$(_GC_STATUS="$STATUS_FILE_WIN" _GC_CARD="$CARD_ID" $PYTHON_CMD -c "
import json, os
with open(os.environ['_GC_STATUS']) as f:
    data = json.load(f)
cards = data.get('cards', [])
card = next((c for c in cards if c.get('card_id') == os.environ['_GC_CARD']), {}) if isinstance(cards, list) else cards.get(os.environ['_GC_CARD'], {})
print(card.get('assurance', 'none'))
" 2>/dev/null || echo "none")
fi

# Build witness chain (TruthCert-style provenance)
WITNESSES=$(_GC_BASE="$PROOFPACK_DIR_WIN/artifacts" $PYTHON_CMD << 'PYEOF'
import os
import json
import hashlib
from datetime import datetime

witnesses = []
base = os.environ.get("_GC_BASE", "")

# Witness for each artifact with hash
if base and os.path.exists(base):
    for root, dirs, files in os.walk(base):
        for f in files:
            path = os.path.join(root, f)
            rel_path = os.path.relpath(path, base)
            try:
                with open(path, 'rb') as fh:
                    content_hash = hashlib.sha256(fh.read()).hexdigest()
                witnesses.append({
                    "source_type": "file",
                    "locator": rel_path,
                    "content_hash": content_hash,
                    "timestamp": datetime.now().isoformat(),
                    "grade": "A"  # Direct file evidence
                })
            except:
                pass

print(json.dumps(witnesses))
PYEOF
)

# Compute manifest hash for capsule ID (computed after manifest is built)
cat > "$MANIFEST_TMP" << EOF
{
  "truthcert": {
    "spec_version": "1.0.0",
    "capsule_id": null,
    "assurance_level": "$ASSURANCE",
    "fail_closed": true
  },
  "spec_version": "$SPEC_VERSION",
  "card_id": "$CARD_ID",
  "created_at": "$CREATED_AT",
  "provenance": {
    "git_sha": "$GIT_SHA",
    "git_branch": "$GIT_BRANCH",
    "machine_id": "$MACHINE_ID"
  },
  "run_ids": $RUN_IDS,
  "artifacts": $ARTIFACTS_LIST,
  "witnesses": $WITNESSES,
  "evidence_paths": $EVIDENCE_PATHS,
  "validation": {
    "gates": $GATES,
    "validators": $VALIDATORS
  },
  "disclosures": {
    "witness_count": $(echo "$WITNESSES" | $PYTHON_CMD -c "import sys,json; print(len(json.loads(sys.stdin.read())))" 2>/dev/null || echo "0"),
    "validator_version": "$SPEC_VERSION",
    "reproducible": true
  },
  "outputs": {
    "proofpack_path": "$PROOFPACK_DIR",
    "zip_path": $([ "$NO_ZIP" = true ] && echo 'null' || echo "\"$PROOFPACK_DIR/proofpack.zip\"")
  }
}
EOF

# Compute and update capsule_id (using env var pattern to avoid path injection)
MANIFEST_TMP_WIN=$(to_win_path "$MANIFEST_TMP")
CAPSULE_ID=$(_TC_MANIFEST="$MANIFEST_TMP_WIN" $PYTHON_CMD << 'PYEOF'
import hashlib, json, os
manifest_path = os.environ.get("_TC_MANIFEST", "")
try:
    with open(manifest_path) as f:
        data = json.load(f)
    # Remove capsule_id for hashing
    data['truthcert']['capsule_id'] = None
    content = json.dumps(data, sort_keys=True)
    print(hashlib.sha256(content.encode()).hexdigest()[:16])
except Exception as e:
    print("unknown")
PYEOF
)

# Update manifest with capsule_id (using env var pattern)
_TC_MANIFEST="$MANIFEST_TMP_WIN" \
_TC_CAPSULE_ID="$CAPSULE_ID" \
$PYTHON_CMD << 'PYEOF'
import json, os
manifest_path = os.environ.get("_TC_MANIFEST", "")
capsule_id = os.environ.get("_TC_CAPSULE_ID", "unknown")
try:
    with open(manifest_path, 'r') as f:
        data = json.load(f)
    data['truthcert']['capsule_id'] = capsule_id
    with open(manifest_path, 'w') as f:
        json.dump(data, f, indent=2)
except Exception as e:
    pass
PYEOF

sync "$MANIFEST_TMP" 2>/dev/null || true
mv "$MANIFEST_TMP" "$MANIFEST_FILE"

echo ""
echo "Manifest created: $MANIFEST_FILE"

# Create zip if requested
if [ "$NO_ZIP" = false ]; then
    echo ""
    echo "Creating zip archive..."

    ZIP_FILE="$PROOFPACK_DIR/proofpack.zip"

    # Use zip if available, otherwise tar
    if command -v zip &> /dev/null; then
        (cd "$PROOFPACK_DIR" && zip -r proofpack.zip manifest.json artifacts/ 2>/dev/null)
        echo "  Created: $ZIP_FILE"
    else
        TAR_FILE="$PROOFPACK_DIR/proofpack.tar.gz"
        (cd "$PROOFPACK_DIR" && tar -czf proofpack.tar.gz manifest.json artifacts/ 2>/dev/null)
        echo "  Created: $TAR_FILE (zip not available, used tar)"
    fi
fi

# Update gates.proofpack in status (quoted heredoc + env vars to avoid injection)
_GC_STATUS_FILE="$STATUS_FILE_WIN" \
_GC_CARD_ID="$CARD_ID" \
$PYTHON_CMD << 'PYEOF'
import json
import os
from datetime import datetime

status_file = os.environ["_GC_STATUS_FILE"]
card_id = os.environ["_GC_CARD_ID"]

try:
    with open(status_file, 'r') as f:
        status = json.load(f)

    # cards is an array of objects, not a dict
    cards = status.get('cards', [])
    if isinstance(cards, list):
        for c in cards:
            if c.get('card_id') == card_id:
                if 'gates' not in c:
                    c['gates'] = {}
                # Use dict format consistent with tower_gatecheck.sh
                c['gates']['proofpack'] = {'status': 'PASS', 'severity': 'P1'}
                c['updated_at'] = datetime.now().isoformat()
                break
    elif isinstance(cards, dict) and card_id in cards:
        if 'gates' not in cards[card_id]:
            cards[card_id]['gates'] = {}
        # Use dict format consistent with tower_gatecheck.sh
        cards[card_id]['gates']['proofpack'] = {'status': 'PASS', 'severity': 'P1'}
        cards[card_id]['updated_at'] = datetime.now().isoformat()

    status['cards'] = cards
    status['last_updated'] = datetime.now().isoformat()

    tmp_file = status_file + '.tmp'
    with open(tmp_file, 'w') as f:
        json.dump(status, f, indent=2)

    os.replace(tmp_file, status_file)
    print("Status updated: gates.proofpack = PASS")
except Exception as e:
    print(f"Warning: Could not update status: {e}")
PYEOF

echo ""
echo "============================================================"
echo "Proofpack complete: $PROOFPACK_DIR"
echo "============================================================"
