#!/usr/bin/env bash
#
# Tower Capacity Pilot
# Analyzes capacity over 14 days and updates baseline.
#
# Usage:
#   tower_capacity_pilot.sh [--days N]
#
# Output:
#   tower/control/capacity_report.md
#   tower/control/capacity_baseline.json (updated atomically)
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

# Parse arguments
DAYS=14
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
echo "Tower Capacity Pilot"
echo "Analysis period: $DAYS days"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"

$PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

tower_root = Path(os.environ.get('TOWER_ROOT', Path(__file__).parent.parent))
days = int(os.environ.get('DAYS', 14))
spec_version = "v1.5.5"

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

artifacts_dir = tower_root / "artifacts"
baseline_file = tower_root / "control" / "capacity_baseline.json"
report_file = tower_root / "control" / "capacity_report.md"

# Date range
end_date = datetime.now()
start_date = end_date - timedelta(days=days)

print()
print(f"Analyzing capacity from {start_date.date()} to {end_date.date()}...")
print()

# Collect data
cards_per_day = defaultdict(set)
run_durations = []
runs_by_date = defaultdict(int)

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

        date_str = date_dir.name

        for card_dir in date_dir.iterdir():
            if not card_dir.is_dir():
                continue

            cards_per_day[date_str].add(card_dir.name)

            for run_dir in card_dir.iterdir():
                if not run_dir.is_dir():
                    continue

                runs_by_date[date_str] += 1

                summary_file = run_dir / "run_summary.json"
                if summary_file.exists():
                    try:
                        with open(summary_file) as f:
                            summary = json.load(f)
                        duration = summary.get("duration_seconds", 0)
                        if duration > 0:
                            run_durations.append(duration)
                    except:
                        pass

# Calculate statistics
cards_counts = [len(cards) for cards in cards_per_day.values()]
if cards_counts:
    mean_cards = sum(cards_counts) / len(cards_counts)
    sorted_counts = sorted(cards_counts)
    median_cards = sorted_counts[len(sorted_counts) // 2]
    min_cards = min(cards_counts)
    max_cards = max(cards_counts)
else:
    mean_cards = median_cards = min_cards = max_cards = 0

if run_durations:
    avg_duration = sum(run_durations) / len(run_durations)
else:
    avg_duration = 0

# Load status for gate pass rate
status = load_json(tower_root / "control" / "status.json")
cards = status.get("cards", {})
total_cards = len(cards)
green_cards = sum(1 for c in cards.values() if c.get("color") == "GREEN")
escalated_cards = sum(1 for c in cards.values() if c.get("state") == "ESCALATED")

gate_pass_rate = green_cards / total_cards if total_cards > 0 else None
escalation_rate = escalated_cards / total_cards if total_cards > 0 else None

print("Capacity Analysis Results:")
print(f"  Cards per day: mean={mean_cards:.1f}, median={median_cards}, range=[{min_cards}, {max_cards}]")
print(f"  Total runs analyzed: {len(run_durations)}")
print(f"  Average run duration: {avg_duration:.1f}s")
print(f"  Gate pass rate: {gate_pass_rate*100:.1f}%" if gate_pass_rate else "  Gate pass rate: N/A")
print(f"  Escalation rate: {escalation_rate*100:.1f}%" if escalation_rate else "  Escalation rate: N/A")
print()

# Update baseline
baseline = {
    "spec_version": spec_version,
    "last_updated": datetime.now().isoformat(),
    "analysis_period_days": days,
    "cards_per_day": {
        "mean": mean_cards if cards_counts else None,
        "median": median_cards if cards_counts else None,
        "min": min_cards if cards_counts else None,
        "max": max_cards if cards_counts else None
    },
    "avg_time_per_state_minutes": {
        "READY": None,
        "ACTIVE": None,
        "REVIEW": None,
        "BLOCKED": None,
        "GATES_PASS": None,
        "VALIDATORS_PASS": None,
        "GOLD": None
    },
    "quota_utilization": {},
    "gate_pass_rate": gate_pass_rate,
    "escalation_rate": escalation_rate,
    "drift_incidents_per_day": None
}

# Atomic write baseline
tmp_file = str(baseline_file) + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(baseline, f, indent=2)
os.replace(tmp_file, str(baseline_file))

print(f"Baseline updated: {baseline_file}")

# Generate report
report = f"""# Tower Capacity Report

**Generated:** {datetime.now().isoformat()}
**Analysis Period:** {days} days ({start_date.date()} to {end_date.date()})
**Spec Version:** {spec_version}

## Summary

| Metric | Value |
|--------|-------|
| Cards per day (mean) | {mean_cards:.1f} |
| Cards per day (median) | {median_cards} |
| Cards per day (range) | {min_cards} - {max_cards} |
| Total runs analyzed | {len(run_durations)} |
| Average run duration | {avg_duration:.1f}s |
| Gate pass rate | {f'{gate_pass_rate*100:.1f}%' if gate_pass_rate is not None else 'N/A'} |
| Escalation rate | {f'{escalation_rate*100:.1f}%' if escalation_rate is not None else 'N/A'} |

## Daily Activity

| Date | Cards | Runs |
|------|-------|------|
"""

for date_str in sorted(cards_per_day.keys(), reverse=True)[:14]:
    card_count = len(cards_per_day[date_str])
    run_count = runs_by_date[date_str]
    report += f"| {date_str} | {card_count} | {run_count} |\n"

report += """

## Recommendations

1. Monitor cards per day trend to ensure consistent throughput
2. Investigate days with zero cards for potential blockers
3. Review escalated cards for systemic issues

---
*Generated by Tower Capacity Pilot*
"""

with open(report_file, 'w') as f:
    f.write(report)

print(f"Report generated: {report_file}")
PYTHON_SCRIPT

echo ""
echo "============================================================"
echo "Capacity analysis complete"
echo "============================================================"
