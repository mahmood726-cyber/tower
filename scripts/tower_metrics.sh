#!/usr/bin/env bash
#
# Tower Metrics Collector
# Collects and appends metrics to tower/control/metrics.csv
#
# Usage:
#   tower_metrics.sh
#
# Metrics collected:
#   - cards_completed
#   - gate_pass_rate
#   - drift_incidents
#   - quota_pct
#   - avg_time_in_state (placeholder)
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

METRICS_FILE="$TOWER_ROOT/control/metrics.csv"
STATUS_FILE="$TOWER_ROOT/control/status.json"
QUOTA_FILE="$TOWER_ROOT/control/quota.json"
DRIFT_LOG="$TOWER_ROOT/control/alerts/drift_log.csv"

echo "============================================================"
echo "Tower Metrics Collector"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"

# Initialize metrics file if not exists
if [ ! -f "$METRICS_FILE" ]; then
    echo "timestamp,cards_total,cards_completed,cards_active,cards_blocked,gate_pass_rate,drift_incidents_today,avg_quota_pct,placeholder" > "$METRICS_FILE"
fi

$PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
from datetime import datetime, date
from pathlib import Path

tower_root = Path(os.environ.get('TOWER_ROOT', Path(__file__).parent.parent))

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

status = load_json(tower_root / "control" / "status.json")
quota = load_json(tower_root / "control" / "quota.json")

now = datetime.now().isoformat()
today = date.today().isoformat()

# Count cards
cards = status.get("cards", {})
cards_total = len(cards)
cards_completed = sum(1 for c in cards.values() if c.get("state") == "MERGED")
cards_active = sum(1 for c in cards.values() if c.get("state") == "ACTIVE")
cards_blocked = sum(1 for c in cards.values() if c.get("state") in ("BLOCKED", "ESCALATED"))

# Calculate gate pass rate
green_count = sum(1 for c in cards.values() if c.get("color") == "GREEN")
gate_pass_rate = (green_count / cards_total * 100) if cards_total > 0 else 0

# Count drift incidents today
drift_incidents = 0
drift_log = tower_root / "control" / "alerts" / "drift_log.csv"
if drift_log.exists():
    with open(drift_log) as f:
        for line in f:
            if line.startswith(today):
                drift_incidents += 1

# Calculate average quota utilization
models = quota.get("models", {})
quota_pcts = []
for model in models.values():
    daily_limit = model.get("daily_limit", 0)
    used_today = model.get("used_today", 0)
    if daily_limit > 0:
        quota_pcts.append(used_today / daily_limit * 100)

avg_quota_pct = sum(quota_pcts) / len(quota_pcts) if quota_pcts else 0

# Print metrics
print()
print("Metrics collected:")
print(f"  Cards total: {cards_total}")
print(f"  Cards completed: {cards_completed}")
print(f"  Cards active: {cards_active}")
print(f"  Cards blocked: {cards_blocked}")
print(f"  Gate pass rate: {gate_pass_rate:.1f}%")
print(f"  Drift incidents today: {drift_incidents}")
print(f"  Avg quota utilization: {avg_quota_pct:.1f}%")
print()

# Append to metrics file
metrics_file = tower_root / "control" / "metrics.csv"
with open(metrics_file, 'a') as f:
    f.write(f"{now},{cards_total},{cards_completed},{cards_active},{cards_blocked},{gate_pass_rate:.2f},{drift_incidents},{avg_quota_pct:.2f},true\n")

print(f"Metrics appended to: {metrics_file}")
PYTHON_SCRIPT

echo ""
echo "============================================================"
echo "Metrics collection complete"
echo "============================================================"
