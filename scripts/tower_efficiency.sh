#!/usr/bin/env bash
#
# Tower Efficiency Analyzer
# Analyzes quota utilization and backlog to suggest optimizations.
#
# Usage:
#   tower_efficiency.sh
#
# Output:
#   tower/control/alerts/efficiency_alerts.json
#   tower/control/alerts/efficiency_log.csv
#
# This is a STUB that provides recommendations without executing them.
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

QUOTA_FILE="$TOWER_ROOT/control/quota.json"
BACKLOG_FILE="$TOWER_ROOT/control/backlog.json"
ALERTS_FILE="$TOWER_ROOT/control/alerts/efficiency_alerts.json"
LOG_FILE="$TOWER_ROOT/control/alerts/efficiency_log.csv"

mkdir -p "$TOWER_ROOT/control/alerts"

echo "============================================================"
echo "Tower Efficiency Analyzer"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"

# Initialize log if not exists
if [ ! -f "$LOG_FILE" ]; then
    echo "timestamp,metric,value,recommendation" > "$LOG_FILE"
fi

$PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
from datetime import datetime
from pathlib import Path

tower_root = Path(os.environ.get('TOWER_ROOT', Path(__file__).parent.parent))
spec_version = "v1.5.5"

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

quota = load_json(tower_root / "control" / "quota.json")
backlog = load_json(tower_root / "control" / "backlog.json")

alerts = []
log_entries = []
now = datetime.now().isoformat()

print()
print("Analyzing efficiency...")
print()

# Check quota utilization
models = quota.get("models", {})
for model_id, model in models.items():
    daily_limit = model.get("daily_limit", 0)
    used_today = model.get("used_today", 0)
    target = model.get("targets", {}).get("daily_utilization", 0.9)

    if daily_limit > 0:
        utilization = used_today / daily_limit
        target_usage = daily_limit * target

        print(f"Model: {model_id}")
        print(f"  Usage: {used_today}/{daily_limit} ({utilization*100:.1f}%)")
        print(f"  Target: {target*100:.0f}% ({target_usage:.0f})")

        if utilization < target * 0.5:
            recommendation = f"Underutilized: assign more work to {model_id}"
            alerts.append({
                "type": "quota_underutilized",
                "model": model_id,
                "utilization": utilization,
                "target": target,
                "message": recommendation,
                "timestamp": now
            })
            log_entries.append(f"{now},quota_utilization,{utilization:.3f},{recommendation}")
            print(f"  ALERT: {recommendation}")
        elif utilization > target:
            recommendation = f"Near limit: consider redistributing from {model_id}"
            print(f"  INFO: {recommendation}")

        print()

# Check backlog health
streams = backlog.get("streams", {})
for stream_name, stream in streams.items():
    ready = stream.get("ready_cards", [])
    active = stream.get("active_cards", [])
    blocked = stream.get("blocked_cards", [])
    minimum = stream.get("minimum_ready", 3)

    print(f"Stream: {stream_name}")
    print(f"  Ready: {len(ready)} (minimum: {minimum})")
    print(f"  Active: {len(active)}")
    print(f"  Blocked: {len(blocked)}")

    if len(ready) < minimum:
        recommendation = f"Low backlog in {stream_name}: add more READY cards"
        alerts.append({
            "type": "low_backlog",
            "stream": stream_name,
            "ready_count": len(ready),
            "minimum": minimum,
            "message": recommendation,
            "timestamp": now
        })
        log_entries.append(f"{now},backlog_ready,{len(ready)},{recommendation}")
        print(f"  ALERT: {recommendation}")

    if len(blocked) > 0:
        recommendation = f"Blocked cards in {stream_name}: investigate blockers"
        print(f"  WARNING: {recommendation}")

    print()

# Check for idle windows
print("Recommendations:")
if len(alerts) == 0:
    print("  No efficiency issues detected.")
else:
    for alert in alerts:
        print(f"  - {alert['message']}")

# Write alerts
alerts_file = tower_root / "control" / "alerts" / "efficiency_alerts.json"
with open(str(alerts_file) + ".tmp", 'w') as f:
    json.dump({"spec_version": spec_version, "generated_at": now, "alerts": alerts}, f, indent=2)
os.replace(str(alerts_file) + ".tmp", str(alerts_file))

# Append to log
log_file = tower_root / "control" / "alerts" / "efficiency_log.csv"
if log_entries:
    with open(log_file, 'a') as f:
        for entry in log_entries:
            f.write(entry + "\n")

print()
print(f"Alerts: {len(alerts)}")
print(f"Output: {alerts_file}")
PYTHON_SCRIPT

echo ""
echo "============================================================"
echo "Efficiency analysis complete"
echo "============================================================"
