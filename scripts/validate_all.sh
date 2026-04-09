#!/usr/bin/env bash
#
# Tower Validation Script
# Runs all validation checks for Tower control files
#
# Usage: ./validate_all.sh
# Exit codes:
#   0 - All validations passed
#   1 - Validation errors found
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$SCRIPT_DIR")"

echo "============================================================"
echo "Tower Full Validation"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "Tower root: $TOWER_ROOT"
echo "============================================================"
echo

ERRORS=0

# Detect Python command (python3 or python)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Neither python3 nor python found"
    exit 1
fi

# Step 1: Check if jq is available
echo "Step 1: Checking dependencies..."
if ! command -v jq &> /dev/null; then
    echo "  WARNING: jq is not installed. JSON syntax checks will be limited."
    JQ_AVAILABLE=0
else
    echo "  jq: available ($(jq --version))"
    JQ_AVAILABLE=1
fi

echo "  python: available ($($PYTHON_CMD --version))"
echo

# Step 2: Run Python schema validator
echo "Step 2: Running schema validation..."
if $PYTHON_CMD "$SCRIPT_DIR/validate_control_files.py"; then
    echo "  Schema validation: PASSED"
else
    echo "  Schema validation: FAILED"
    ERRORS=$((ERRORS + 1))
fi
echo

# Step 3: JSON syntax check with jq
if [ "$JQ_AVAILABLE" -eq 1 ]; then
    echo "Step 3: Running jq syntax checks..."

    FAILED_FILES=""

    # Check control directory
    if [ -d "$TOWER_ROOT/control" ]; then
        while IFS= read -r -d '' jsonfile; do
            if ! jq empty "$jsonfile" 2>/dev/null; then
                echo "  FAIL: $jsonfile"
                FAILED_FILES="$FAILED_FILES $jsonfile"
            fi
        done < <(find "$TOWER_ROOT/control" -name "*.json" -print0 2>/dev/null)
    fi

    # Check papers directory
    if [ -d "$TOWER_ROOT/papers" ]; then
        while IFS= read -r -d '' jsonfile; do
            if ! jq empty "$jsonfile" 2>/dev/null; then
                echo "  FAIL: $jsonfile"
                FAILED_FILES="$FAILED_FILES $jsonfile"
            fi
        done < <(find "$TOWER_ROOT/papers" -name "*.json" -print0 2>/dev/null)
    fi

    if [ -z "$FAILED_FILES" ]; then
        echo "  jq syntax check: PASSED"
    else
        echo "  jq syntax check: FAILED"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "Step 3: Skipping jq syntax checks (jq not available)"
fi
echo

# Step 4: Check critical files exist
echo "Step 4: Checking critical files..."
CRITICAL_FILES=(
    "control/status.json"
    "control/quota.json"
    "control/machines.json"
    "control/backlog.json"
    "control/drift_config.json"
)

MISSING=0
for file in "${CRITICAL_FILES[@]}"; do
    filepath="$TOWER_ROOT/$file"
    if [ -f "$filepath" ]; then
        echo "  [+] $file"
    else
        echo "  [X] $file (MISSING)"
        MISSING=$((MISSING + 1))
    fi
done

if [ $MISSING -gt 0 ]; then
    echo "  WARNING: $MISSING critical files missing"
fi
echo

# Final result
echo "============================================================"
if [ $ERRORS -eq 0 ]; then
    echo "RESULT: ALL VALIDATIONS PASSED"
    exit 0
else
    echo "RESULT: VALIDATION FAILED ($ERRORS errors)"
    exit 1
fi
