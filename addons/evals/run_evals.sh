#!/usr/bin/env bash
#
# Tower Evals Runner (shell wrapper)
#
# Usage:
#   bash tower/addons/evals/run_evals.sh [--all|--list|--case EV-000]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Neither python3 nor python found"
    exit 1
fi

# Run evals
exec "$PYTHON_CMD" "$SCRIPT_DIR/run_evals.py" "$@"
