#!/usr/bin/env bash
#
# Tower Capsule Creator
# Creates a TruthCert capsule (immutable proof bundle) per Spec v0.8 Section 25.
#
# Usage:
#   capsule_create.sh --domain DOMAIN --topic TOPIC [--lanes map,meta] [--dry-run]
#
# Creates:
#   capsules/<date>/<domain>-<topic>/
#     - MANIFEST.json (capsule_id = sha256)
#     - GRAPH/
#     - OUTPUT/
#     - VIEWS/
#     - VALIDATION/
#     - LINEAGE/
#     - EXPLAIN.json
#     - NUMBER_CARD.json (if applicable)
#     - PROVENANCE.md
#     - CHANGELOG.md
#     - CITATION.cff
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

# Parse arguments
DOMAIN=""
TOPIC=""
LANES="map"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --topic)
            TOPIC="$2"
            shift 2
            ;;
        --lanes)
            LANES="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$DOMAIN" ] || [ -z "$TOPIC" ]; then
    echo "ERROR: --domain and --topic are required"
    echo "Usage: capsule_create.sh --domain cardiology --topic sglt2i [--lanes map,meta]"
    exit 1
fi

# Validate domain/topic format (prevent injection)
if ! echo "$DOMAIN" | grep -qE '^[a-z0-9_-]+$'; then
    echo "ERROR: --domain must be lowercase alphanumeric with underscores/dashes"
    exit 1
fi

if ! echo "$TOPIC" | grep -qE '^[a-z0-9_-]+$'; then
    echo "ERROR: --topic must be lowercase alphanumeric with underscores/dashes"
    exit 1
fi

DATE_DIR=$(date +%Y-%m-%d)
CAPSULE_NAME="${DOMAIN}-${TOPIC}"
CAPSULE_DIR="$TOWER_ROOT/capsules/$DATE_DIR/$CAPSULE_NAME"

echo "============================================================"
echo "Tower Capsule Creator"
echo "Domain: $DOMAIN"
echo "Topic: $TOPIC"
echo "Lanes: $LANES"
echo "Output: $CAPSULE_DIR"
echo "Mode: $([ "$DRY_RUN" = true ] && echo 'DRY RUN' || echo 'EXECUTE')"
echo "============================================================"

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "DRY RUN: Would create capsule at $CAPSULE_DIR"
    exit 0
fi

# Create capsule directory structure
mkdir -p "$CAPSULE_DIR/GRAPH"
mkdir -p "$CAPSULE_DIR/OUTPUT"
mkdir -p "$CAPSULE_DIR/VIEWS"
mkdir -p "$CAPSULE_DIR/VALIDATION"
mkdir -p "$CAPSULE_DIR/LINEAGE"

# Get git info
GIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
MACHINE_ID="${TOWER_MACHINE:-$(hostname 2>/dev/null || echo 'unknown')}"

# Get machine role
MACHINE_ROLE="dev"
if [ -f "$TOWER_ROOT/control/machine_config.json" ]; then
    MACHINE_ROLE=$($PYTHON_CMD -c "
import json
with open('$TOWER_ROOT/control/machine_config.json') as f:
    print(json.load(f).get('role', 'dev'))
" 2>/dev/null || echo "dev")
fi

RUN_ID="run:$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S):${GIT_SHA:0:7}:$MACHINE_ID"

echo ""
echo "Creating capsule structure..."

# Create EXPLAIN.json
cat > "$CAPSULE_DIR/EXPLAIN.json" << EOF
{
  "spec_version": "$SPEC_VERSION",
  "capsule_id": null,
  "generated_at": "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S)",
  "badge": {
    "level": "bronze",
    "algorithm_version": "$SPEC_VERSION",
    "computation_summary": "Initial capsule creation"
  },
  "validators_summary": {
    "total_run": 0,
    "p0_blockers": 0,
    "p1_warnings": 0,
    "p2_info": 0
  },
  "top_blockers": [],
  "top_drift_changes": [],
  "conflicts_open": 0,
  "conflicts_resolved": 0,
  "abstentions_count": 0,
  "certainty_summary": {
    "certainty_level": "low",
    "top_drivers": ["Initial creation - no validation yet"],
    "top_concerns": []
  },
  "next_actions": [
    {
      "action_type": "witness_needed",
      "description": "Add witnesses from registry/publication sources",
      "priority": "P1"
    }
  ],
  "incidents": [],
  "release_notes": "Initial capsule for $DOMAIN/$TOPIC"
}
EOF

# Create PROVENANCE.md
cat > "$CAPSULE_DIR/PROVENANCE.md" << EOF
# Provenance

## Capsule Information
- **Domain:** $DOMAIN
- **Topic:** $TOPIC
- **Created:** $(date -Iseconds 2>/dev/null || date)
- **Spec Version:** $SPEC_VERSION

## Run Information
- **Run ID:** $RUN_ID
- **Machine ID:** $MACHINE_ID
- **Machine Role:** $MACHINE_ROLE
- **Git SHA:** $GIT_SHA
- **Git Branch:** $GIT_BRANCH

## Lanes Included
$(echo "$LANES" | tr ',' '\n' | while read lane; do echo "- $lane"; done)

## Witnesses
No witnesses captured yet.

## Validation
No validators run yet.
EOF

# Create CHANGELOG.md
cat > "$CAPSULE_DIR/CHANGELOG.md" << EOF
# Changelog

## $(date +%Y-%m-%d) - Initial Creation

- Created capsule for $DOMAIN/$TOPIC
- Lanes: $LANES
- Status: Bronze (Map-grade)

---
*Generated by Tower Capsule Creator*
EOF

# Create CITATION.cff
cat > "$CAPSULE_DIR/CITATION.cff" << EOF
cff-version: 1.2.0
message: "If you use this evidence capsule, please cite it as below."
title: "TruthCert Evidence Capsule: $DOMAIN - $TOPIC"
version: "1.0.0"
date-released: $(date +%Y-%m-%d)
repository-code: "https://github.com/example/tower"
license: "CC-BY-4.0"
type: dataset
keywords:
  - evidence synthesis
  - meta-analysis
  - $DOMAIN
  - $TOPIC
EOF

# Create placeholder NUMBER_CARD.json
cat > "$CAPSULE_DIR/NUMBER_CARD.json" << EOF
{
  "spec_version": "$SPEC_VERSION",
  "number_card_id": "nc:${DOMAIN}:${TOPIC}:placeholder",
  "capsule_id": null,
  "label": "Placeholder - no numbers published yet",
  "context": {
    "domain": "$DOMAIN",
    "outcome": null,
    "comparison": null,
    "population": null
  },
  "value": null,
  "uncertainty": null,
  "badge": {
    "level": "none"
  },
  "witnesses": {
    "count": 0,
    "grades": {"A": 0, "B": 0, "C": 0},
    "locators": []
  },
  "consensus_rule": null,
  "known_limitations": ["No data extracted yet"],
  "warnings": [],
  "generated_at": "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S)"
}
EOF

# Create MANIFEST.json (without capsule_id first)
MANIFEST_TMP="$CAPSULE_DIR/MANIFEST.json.tmp"
cat > "$MANIFEST_TMP" << EOF
{
  "spec_version": "$SPEC_VERSION",
  "capsule_id": null,
  "created_at": "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S)",
  "domain": "$DOMAIN",
  "topic": "$TOPIC",
  "provenance": {
    "run_id": "$RUN_ID",
    "machine_id": "$MACHINE_ID",
    "machine_role": "$MACHINE_ROLE",
    "git_sha": "$GIT_SHA",
    "git_branch": "$GIT_BRANCH",
    "pipeline_version": "$SPEC_VERSION"
  },
  "contents": {
    "graph_dir": "GRAPH/",
    "output_dir": "OUTPUT/",
    "views_dir": "VIEWS/",
    "validation_dir": "VALIDATION/",
    "lineage_dir": "LINEAGE/",
    "outputs": {},
    "explain_json": "EXPLAIN.json",
    "number_cards": ["NUMBER_CARD.json"],
    "provenance_md": "PROVENANCE.md",
    "changelog_md": "CHANGELOG.md",
    "citation_cff": "CITATION.cff"
  },
  "validation": {
    "badge": "bronze",
    "badge_algorithm_version": "$SPEC_VERSION",
    "p0_count": 0,
    "p1_count": 0,
    "p2_count": 0,
    "validators_run": [],
    "all_p0_passed": true
  },
  "lanes_included": [$(echo "$LANES" | tr ',' '\n' | while read lane; do echo "\"$lane\""; done | paste -sd, -)],
  "dependencies": [],
  "signatures": [],
  "sensitivity_tag": "public"
}
EOF

# Compute capsule_id and update manifest
CAPSULE_ID=$(_CC_MANIFEST_TMP="$MANIFEST_TMP" $PYTHON_CMD -c "
import hashlib
import json
import os
manifest_path = os.environ['_CC_MANIFEST_TMP']
with open(manifest_path) as f:
    data = json.load(f)
data['capsule_id'] = None
content = json.dumps(data, sort_keys=True)
print('capsule:' + hashlib.sha256(content.encode()).hexdigest())
")

_CC_MANIFEST_TMP="$MANIFEST_TMP" \
_CC_CAPSULE_ID="$CAPSULE_ID" \
_CC_CAPSULE_DIR="$CAPSULE_DIR" \
$PYTHON_CMD << 'PYEOF'
import json
import os

manifest_tmp = os.environ["_CC_MANIFEST_TMP"]
capsule_id = os.environ["_CC_CAPSULE_ID"]
capsule_dir = os.environ["_CC_CAPSULE_DIR"]

with open(manifest_tmp, 'r') as f:
    data = json.load(f)
data['capsule_id'] = capsule_id
with open(os.path.join(capsule_dir, 'MANIFEST.json'), 'w') as f:
    json.dump(data, f, indent=2)
PYEOF

rm -f "$MANIFEST_TMP"

# Update EXPLAIN.json with capsule_id
_CC_CAPSULE_ID="$CAPSULE_ID" \
_CC_CAPSULE_DIR="$CAPSULE_DIR" \
$PYTHON_CMD << 'PYEOF'
import json
import os

capsule_id = os.environ["_CC_CAPSULE_ID"]
capsule_dir = os.environ["_CC_CAPSULE_DIR"]

with open(os.path.join(capsule_dir, 'EXPLAIN.json'), 'r') as f:
    data = json.load(f)
data['capsule_id'] = capsule_id
with open(os.path.join(capsule_dir, 'EXPLAIN.json'), 'w') as f:
    json.dump(data, f, indent=2)
PYEOF

# Update NUMBER_CARD.json with capsule_id
_CC_CAPSULE_ID="$CAPSULE_ID" \
_CC_CAPSULE_DIR="$CAPSULE_DIR" \
$PYTHON_CMD << 'PYEOF'
import json
import os

capsule_id = os.environ["_CC_CAPSULE_ID"]
capsule_dir = os.environ["_CC_CAPSULE_DIR"]

with open(os.path.join(capsule_dir, 'NUMBER_CARD.json'), 'r') as f:
    data = json.load(f)
data['capsule_id'] = capsule_id
with open(os.path.join(capsule_dir, 'NUMBER_CARD.json'), 'w') as f:
    json.dump(data, f, indent=2)
PYEOF

echo ""
echo "============================================================"
echo "Capsule Created"
echo "============================================================"
echo ""
echo "Capsule ID: $CAPSULE_ID"
echo "Location: $CAPSULE_DIR"
echo ""
echo "Contents:"
ls -la "$CAPSULE_DIR"
echo ""
echo "Next steps:"
echo "  1. Add data to GRAPH/"
echo "  2. Run validators: lane_run.sh --lane map --topic $TOPIC"
echo "  3. Add witnesses from sources"
echo "  4. Regenerate capsule with updated data"
echo ""
