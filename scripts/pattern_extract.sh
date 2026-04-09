#!/usr/bin/env bash
#
# Tower Pattern Extractor
# Extracts failure patterns from FAIL artifacts for learning.
#
# Usage:
#   pattern_extract.sh [--days N]
#
# Output:
#   tower/patterns/extracted_patterns.json
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

SPEC_VERSION="v1.5.7"

PATTERNS_DIR="$TOWER_ROOT/patterns"
mkdir -p "$PATTERNS_DIR"

# Parse arguments
DAYS=7
while [[ $# -gt 0 ]]; do
    case $1 in
        --days)
            DAYS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "============================================================"
echo "Tower Pattern Extractor"
echo "Looking back: $DAYS days"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"

$PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

tower_root = Path(os.environ.get('TOWER_ROOT', Path(__file__).parent.parent))
days = int(os.environ.get('DAYS', 7))
spec_version = "v1.5.5"

artifacts_dir = tower_root / "artifacts"
patterns_file = tower_root / "patterns" / "extracted_patterns.json"

# Date range
end_date = datetime.now()
start_date = end_date - timedelta(days=days)

print()
print(f"Scanning artifacts from {start_date.date()} to {end_date.date()}...")
print()

failure_patterns = Counter()
failures = []

# Scan artifacts
if artifacts_dir.exists():
    for date_dir in artifacts_dir.iterdir():
        if not date_dir.is_dir():
            continue

        try:
            dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
            if dir_date < start_date or dir_date > end_date:
                continue
        except:
            continue

        for card_dir in date_dir.iterdir():
            if not card_dir.is_dir():
                continue

            for run_dir in card_dir.iterdir():
                if not run_dir.is_dir():
                    continue

                summary_file = run_dir / "run_summary.json"
                stderr_file = run_dir / "stderr.log"

                if summary_file.exists():
                    try:
                        with open(summary_file) as f:
                            summary = json.load(f)

                        if summary.get("exit_code", 0) != 0:
                            failure = {
                                "card_id": card_dir.name,
                                "run_id": run_dir.name.replace("run_", ""),
                                "exit_code": summary.get("exit_code"),
                                "date": date_dir.name
                            }

                            # Extract error patterns from stderr
                            if stderr_file.exists():
                                try:
                                    with open(stderr_file) as f:
                                        stderr = f.read()

                                    # Common error patterns
                                    patterns = [
                                        r"error:\s*(.+)",
                                        r"Error:\s*(.+)",
                                        r"Exception:\s*(.+)",
                                        r"FAILED\s+(.+)",
                                        r"fatal:\s*(.+)",
                                    ]

                                    for pattern in patterns:
                                        matches = re.findall(pattern, stderr, re.IGNORECASE)
                                        for match in matches[:3]:  # Limit matches
                                            clean_match = match[:100].strip()
                                            failure_patterns[clean_match] += 1
                                            if "error_sample" not in failure:
                                                failure["error_sample"] = clean_match
                                except:
                                    pass

                            failures.append(failure)
                    except:
                        pass

print(f"Found {len(failures)} failures")
print()

# Most common patterns
print("Top failure patterns:")
for pattern, count in failure_patterns.most_common(10):
    print(f"  [{count}x] {pattern[:80]}")

print()

# Build output
output = {
    "spec_version": spec_version,
    "generated_at": datetime.now().isoformat(),
    "analysis_period": {
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "days": days
    },
    "summary": {
        "total_failures": len(failures),
        "unique_patterns": len(failure_patterns)
    },
    "top_patterns": [
        {"pattern": p, "count": c}
        for p, c in failure_patterns.most_common(20)
    ],
    "recent_failures": failures[:50]  # Limit to recent 50
}

# Atomic write
tmp_file = str(patterns_file) + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(output, f, indent=2)
os.replace(tmp_file, str(patterns_file))

print(f"Patterns saved to: {patterns_file}")
PYTHON_SCRIPT

echo ""
echo "============================================================"
echo "Pattern extraction complete"
echo "============================================================"
