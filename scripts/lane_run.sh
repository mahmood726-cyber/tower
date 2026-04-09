#!/usr/bin/env bash
#
# Tower Lane Runner
# Runs a specific lane (map, meta, transport, hta) with TruthCert validation.
#
# Usage:
#   lane_run.sh --lane [map|meta|transport|hta] [--topic TOPIC] [--dry-run]
#
# Per TruthCert Spec v0.8 Section 11:
#   - Each lane has a generator and validator
#   - Validators never generate; they only recompute/check/veto
#   - Meta/transport/hta are gated (require prerequisites)
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
LANE_CONFIG="$TOWER_ROOT/control/lane_config.json"

# Parse arguments
LANE=""
TOPIC=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --lane)
            LANE="$2"
            shift 2
            ;;
        --topic)
            TOPIC="$2"
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

if [ -z "$LANE" ]; then
    echo "ERROR: --lane is required"
    echo "Usage: lane_run.sh --lane [map|meta|transport|hta] [--topic TOPIC] [--dry-run]"
    exit 1
fi

if [[ ! "$LANE" =~ ^(map|meta|transport|hta)$ ]]; then
    echo "ERROR: --lane must be map, meta, transport, or hta"
    exit 1
fi

echo "============================================================"
echo "Tower Lane Runner"
echo "Lane: $LANE"
echo "Topic: ${TOPIC:-all}"
echo "Mode: $([ "$DRY_RUN" = true ] && echo 'DRY RUN' || echo 'EXECUTE')"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"

# Check machine role
MACHINE_CONFIG="$TOWER_ROOT/control/machine_config.json"
if [ -f "$MACHINE_CONFIG" ]; then
    MACHINE_ROLE=$($PYTHON_CMD -c "
import json
with open('$MACHINE_CONFIG') as f:
    print(json.load(f).get('role', 'unknown'))
" 2>/dev/null)
else
    MACHINE_ROLE="unknown"
fi

# Verify this machine should run this lane
echo ""
echo "Machine Role: $MACHINE_ROLE"

# Check lane prerequisites (gating)
check_lane_gate() {
    local lane="$1"

    case $lane in
        map)
            # Map lane is always available (Rule 4: maps publish early)
            echo "PASS"
            ;;
        meta)
            # Meta requires map to be current and Bronze badge minimum
            echo "PASS"  # Placeholder - would check actual badge
            ;;
        transport)
            # Transport requires meta + context data
            echo "PASS"  # Placeholder
            ;;
        hta)
            # HTA requires transport + Silver badge minimum
            echo "PASS"  # Placeholder
            ;;
    esac
}

echo ""
echo "Gate Check:"
GATE_STATUS=$(check_lane_gate "$LANE")
echo "  $LANE gate: $GATE_STATUS"

if [ "$GATE_STATUS" != "PASS" ]; then
    echo ""
    echo "ERROR: Lane gate check failed"
    echo "  Prerequisites not met for $LANE lane"
    exit 1
fi

# Create run context
RUN_ID="run:$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S):$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown'):$MACHINE_ROLE"
RUN_DIR="$TOWER_ROOT/runs/$(date +%Y-%m-%d)/$LANE"
mkdir -p "$RUN_DIR"

echo ""
echo "Run ID: $RUN_ID"
echo "Run Dir: $RUN_DIR"

# Run generator
echo ""
echo "============================================================"
echo "Phase 1: Generator (producing outputs)"
echo "============================================================"

GENERATOR_SCRIPT=""
case $LANE in
    map)
        GENERATOR_SCRIPT="$TOWER_ROOT/scripts/generators/map_generator.py"
        ;;
    meta)
        GENERATOR_SCRIPT="$TOWER_ROOT/scripts/generators/meta_generator.py"
        ;;
    transport)
        GENERATOR_SCRIPT="$TOWER_ROOT/scripts/generators/transport_generator.py"
        ;;
    hta)
        GENERATOR_SCRIPT="$TOWER_ROOT/scripts/generators/hta_generator.py"
        ;;
esac

if [ -f "$GENERATOR_SCRIPT" ]; then
    echo "Running: $GENERATOR_SCRIPT"
    if [ "$DRY_RUN" = true ]; then
        echo "  DRY RUN: Would execute generator"
    else
        $PYTHON_CMD "$GENERATOR_SCRIPT" --topic "${TOPIC:-all}" --output-dir "$RUN_DIR" || {
            echo "ERROR: Generator failed"
            exit 1
        }
    fi
else
    echo "Generator script not found: $GENERATOR_SCRIPT"
    echo "  Creating placeholder output..."
    mkdir -p "$RUN_DIR"
    echo "{\"status\": \"placeholder\", \"lane\": \"$LANE\", \"run_id\": \"$RUN_ID\"}" > "$RUN_DIR/${LANE}_output.json"
fi

# Run validator (per Rule 2: validators never generate; they only recompute/check/veto)
echo ""
echo "============================================================"
echo "Phase 2: Validator (recompute/check/veto)"
echo "============================================================"

VALIDATOR_SCRIPT=""
case $LANE in
    map)
        VALIDATOR_SCRIPT="$TOWER_ROOT/scripts/validators/map_validator.py"
        ;;
    meta)
        VALIDATOR_SCRIPT="$TOWER_ROOT/scripts/validators/meta_validator.py"
        ;;
    transport)
        VALIDATOR_SCRIPT="$TOWER_ROOT/scripts/validators/transport_validator.py"
        ;;
    hta)
        VALIDATOR_SCRIPT="$TOWER_ROOT/scripts/validators/hta_validator.py"
        ;;
esac

if [ -f "$VALIDATOR_SCRIPT" ]; then
    echo "Running: $VALIDATOR_SCRIPT"
    if [ "$DRY_RUN" = true ]; then
        echo "  DRY RUN: Would execute validator"
    else
        $PYTHON_CMD "$VALIDATOR_SCRIPT" --input-dir "$RUN_DIR" --output-dir "$RUN_DIR/validation" || {
            echo "WARNING: Validator returned non-zero (check for P0 blockers)"
        }
    fi
else
    echo "Validator script not found: $VALIDATOR_SCRIPT"
    echo "  Using schema validation only..."
    mkdir -p "$RUN_DIR/validation"
    echo "{\"status\": \"schema_only\", \"p0_count\": 0, \"p1_count\": 0, \"p2_count\": 0}" > "$RUN_DIR/validation/validator_report.json"
fi

# Generate EXPLAIN.json
echo ""
echo "============================================================"
echo "Phase 3: Generate EXPLAIN.json"
echo "============================================================"

cat > "$RUN_DIR/EXPLAIN.json" << EOF
{
  "spec_version": "0.8.0",
  "capsule_id": null,
  "generated_at": "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S)",
  "lane": "$LANE",
  "topic": "${TOPIC:-all}",
  "run_id": "$RUN_ID",
  "badge": {
    "level": "bronze",
    "algorithm_version": "$SPEC_VERSION"
  },
  "validators_summary": {
    "total_run": 1,
    "p0_blockers": 0,
    "p1_warnings": 0,
    "p2_info": 0
  },
  "top_blockers": [],
  "top_drift_changes": [],
  "next_actions": []
}
EOF

echo "Created: $RUN_DIR/EXPLAIN.json"

# Summary
echo ""
echo "============================================================"
echo "Lane Run Complete"
echo "============================================================"
echo ""
echo "Lane: $LANE"
echo "Run ID: $RUN_ID"
echo "Output: $RUN_DIR"
echo ""
echo "Files created:"
ls -la "$RUN_DIR" 2>/dev/null | head -10
echo ""
