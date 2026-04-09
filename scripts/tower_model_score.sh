#!/usr/bin/env bash
#
# Tower Model Scorecard Updater
# Updates model_scorecard.json from artifacts and metrics.
#
# Usage:
#   tower_model_score.sh
#
# Updates:
#   tower/control/model_scorecard.json (atomic write)
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

SCORECARD_FILE="$TOWER_ROOT/control/model_scorecard.json"
ARTIFACTS_DIR="$TOWER_ROOT/artifacts"

echo "============================================================"
echo "Tower Model Scorecard Updater"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"

$PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
from datetime import datetime
from pathlib import Path

tower_root = Path(os.environ.get('TOWER_ROOT', Path(__file__).parent.parent))
spec_version = "v1.5.5"

scorecard_file = tower_root / "control" / "model_scorecard.json"
artifacts_dir = tower_root / "artifacts"

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

# Load current scorecard
scorecard = load_json(scorecard_file)
if "models" not in scorecard:
    scorecard = {
        "spec_version": spec_version,
        "last_updated": datetime.now().isoformat(),
        "models": {}
    }

# Scan artifacts for run data
model_stats = {}

if artifacts_dir.exists():
    for date_dir in artifacts_dir.iterdir():
        if not date_dir.is_dir():
            continue
        for card_dir in date_dir.iterdir():
            if not card_dir.is_dir():
                continue
            for run_dir in card_dir.iterdir():
                if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                    continue

                context_file = run_dir / "run_context.json"
                summary_file = run_dir / "run_summary.json"

                if context_file.exists():
                    context = load_json(context_file)
                    model = context.get("model")

                    if model:
                        if model not in model_stats:
                            model_stats[model] = {
                                "total_runs": 0,
                                "successful_runs": 0,
                                "failed_runs": 0,
                                "total_duration": 0,
                                "last_run": None
                            }

                        model_stats[model]["total_runs"] += 1

                        if summary_file.exists():
                            summary = load_json(summary_file)
                            exit_code = summary.get("exit_code", -1)
                            duration = summary.get("duration_seconds", 0)

                            if exit_code == 0:
                                model_stats[model]["successful_runs"] += 1
                            else:
                                model_stats[model]["failed_runs"] += 1

                            model_stats[model]["total_duration"] += duration

                            end_time = summary.get("end_time")
                            if end_time:
                                current_last = model_stats[model]["last_run"]
                                if not current_last or end_time > current_last:
                                    model_stats[model]["last_run"] = end_time

print()
print("Model statistics from artifacts:")

# Update scorecard
for model_id, stats in model_stats.items():
    if model_id not in scorecard["models"]:
        scorecard["models"][model_id] = {"model_id": model_id}

    model = scorecard["models"][model_id]
    model["total_runs"] = stats["total_runs"]
    model["successful_runs"] = stats["successful_runs"]
    model["failed_runs"] = stats["failed_runs"]

    if stats["total_runs"] > 0:
        model["success_rate"] = stats["successful_runs"] / stats["total_runs"]
        model["avg_duration_seconds"] = stats["total_duration"] / stats["total_runs"]
    else:
        model["success_rate"] = None
        model["avg_duration_seconds"] = None

    model["last_run"] = stats["last_run"]

    print(f"  {model_id}:")
    print(f"    Total runs: {stats['total_runs']}")
    print(f"    Success rate: {model.get('success_rate', 0)*100:.1f}%" if model.get('success_rate') else "    Success rate: N/A")

scorecard["last_updated"] = datetime.now().isoformat()
scorecard["spec_version"] = spec_version

# Atomic write
tmp_file = str(scorecard_file) + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(scorecard, f, indent=2)

os.replace(tmp_file, str(scorecard_file))

print()
print(f"Scorecard updated: {scorecard_file}")
PYTHON_SCRIPT

echo ""
echo "============================================================"
echo "Model scorecard update complete"
echo "============================================================"
