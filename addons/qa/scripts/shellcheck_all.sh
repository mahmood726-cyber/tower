#!/usr/bin/env bash
# shellcheck_all.sh - Run ShellCheck on all Tower bash scripts
# Part of Tower v1.5.5 QA Tools
#
# Usage: bash tower/addons/qa/scripts/shellcheck_all.sh [--strict] [--fix]
#
# Options:
#   --strict    Use stricter checking (info level)
#   --fix       Show suggested fixes (requires shellcheck 0.8+)
#   --json      Output JSON format
#   --summary   Only show summary, not individual issues

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default options
SEVERITY="warning"
FORMAT="tty"
SUMMARY_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --strict)
            SEVERITY="info"
            shift
            ;;
        --fix)
            FORMAT="diff"
            shift
            ;;
        --json)
            FORMAT="json"
            shift
            ;;
        --summary)
            SUMMARY_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=== Tower ShellCheck Analysis ==="
echo "Tower root: $TOWER_ROOT"
echo "Severity: $SEVERITY"
echo "Format: $FORMAT"
echo ""

# Check if shellcheck is installed
if ! command -v shellcheck &> /dev/null; then
    echo -e "${RED}ERROR: shellcheck is not installed${NC}"
    echo ""
    echo "Install with:"
    echo "  Ubuntu/Debian: sudo apt-get install shellcheck"
    echo "  macOS:         brew install shellcheck"
    echo "  Windows:       scoop install shellcheck"
    exit 1
fi

SHELLCHECK_VERSION=$(shellcheck --version | head -2 | tail -1)
echo "ShellCheck version: $SHELLCHECK_VERSION"
echo ""

# Find all shell scripts
SCRIPTS=()
while IFS= read -r -d '' script; do
    SCRIPTS+=("$script")
done < <(find "$TOWER_ROOT" -name '*.sh' \
    -not -path '*/.git/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/venv/*' \
    -not -path '*/__pycache__/*' \
    -print0 | sort -z)

TOTAL=${#SCRIPTS[@]}
echo "Found $TOTAL shell scripts"
echo ""

if [[ $TOTAL -eq 0 ]]; then
    echo "No shell scripts found."
    exit 0
fi

# Track results
PASSED=0
WARNED=0
FAILED=0
ERRORS=()

# Check each script
for script in "${SCRIPTS[@]}"; do
    rel_path="${script#$TOWER_ROOT/}"

    if [[ "$SUMMARY_ONLY" == "false" && "$FORMAT" == "tty" ]]; then
        echo -n "Checking $rel_path... "
    fi

    # Run shellcheck
    if shellcheck -x -S "$SEVERITY" -f "$FORMAT" "$script" 2>/dev/null; then
        ((PASSED++))
        if [[ "$SUMMARY_ONLY" == "false" && "$FORMAT" == "tty" ]]; then
            echo -e "${GREEN}OK${NC}"
        fi
    else
        exit_code=$?
        if [[ $exit_code -eq 1 ]]; then
            # Has warnings/errors
            ((WARNED++))
            ERRORS+=("$rel_path")
            if [[ "$SUMMARY_ONLY" == "false" && "$FORMAT" == "tty" ]]; then
                echo -e "${YELLOW}WARNINGS${NC}"
            fi
        else
            # Shellcheck itself failed
            ((FAILED++))
            ERRORS+=("$rel_path (shellcheck error)")
            if [[ "$SUMMARY_ONLY" == "false" && "$FORMAT" == "tty" ]]; then
                echo -e "${RED}ERROR${NC}"
            fi
        fi
    fi
done

# Print summary
echo ""
echo "=== Summary ==="
echo -e "Passed:   ${GREEN}$PASSED${NC}"
echo -e "Warnings: ${YELLOW}$WARNED${NC}"
echo -e "Failed:   ${RED}$FAILED${NC}"
echo "Total:    $TOTAL"
echo ""

if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo "Scripts with issues:"
    for err in "${ERRORS[@]}"; do
        echo "  - $err"
    done
    echo ""
fi

# Calculate pass rate
PASS_RATE=$((PASSED * 100 / TOTAL))
echo "Pass rate: ${PASS_RATE}%"

# Exit with appropriate code
if [[ $FAILED -gt 0 ]]; then
    echo -e "${RED}ShellCheck found critical issues.${NC}"
    exit 2
elif [[ $WARNED -gt 0 ]]; then
    echo -e "${YELLOW}ShellCheck found warnings. Review recommended.${NC}"
    exit 1
else
    echo -e "${GREEN}All scripts passed ShellCheck!${NC}"
    exit 0
fi
