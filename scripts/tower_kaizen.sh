#!/usr/bin/env bash
#
# Tower Kaizen Proposal Generator
# Generates improvement proposals based on metrics analysis.
#
# Usage:
#   tower_kaizen.sh [--days N]
#
# Output:
#   tower/control/kaizen/proposals/YYYY-MM-DD_proposals.json
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

KAIZEN_DIR="$TOWER_ROOT/control/kaizen/proposals"
mkdir -p "$KAIZEN_DIR"

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
echo "Tower Kaizen Proposal Generator"
echo "Analysis period: $DAYS days"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"

$PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import random
import string

tower_root = Path(os.environ.get('TOWER_ROOT', Path(__file__).parent.parent))
days = int(os.environ.get('DAYS', 7))
spec_version = "v1.5.5"

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

def generate_proposal_id():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = ''.join(random.choices(string.ascii_lowercase, k=4))
    return f"KZN_{timestamp}_{suffix}"

# Load metrics
metrics_file = tower_root / "control" / "metrics.csv"
status = load_json(tower_root / "control" / "status.json")
quota = load_json(tower_root / "control" / "quota.json")

print()
print("Analyzing metrics for improvement opportunities...")
print()

proposals = []

# Analyze quota utilization
models = quota.get("models", {})
for model_id, model in models.items():
    daily_limit = model.get("daily_limit", 0)
    used_today = model.get("used_today", 0)
    target = model.get("targets", {}).get("daily_utilization", 0.9)

    if daily_limit > 0:
        utilization = used_today / daily_limit

        if utilization < target * 0.3:
            proposals.append({
                "proposal_id": generate_proposal_id(),
                "title": f"Increase {model_id} utilization",
                "rationale": f"{model_id} is at {utilization*100:.1f}% of daily quota (target: {target*100:.0f}%)",
                "status": "proposed",
                "metrics_before": {
                    "utilization": utilization,
                    "target": target
                },
                "proposed_change": f"Assign more work to {model_id} or increase batch sizes",
                "expected_improvement": f"Increase utilization to {target*100:.0f}%",
                "created_at": datetime.now().isoformat(),
                "spec_version": spec_version,
                "source": "auto"
            })

# Analyze card state distribution
cards = status.get("cards", {})
blocked_count = sum(1 for c in cards.values() if c.get("state") in ("BLOCKED", "ESCALATED"))
total_cards = len(cards)

if blocked_count > 0 and total_cards > 0:
    blocked_pct = blocked_count / total_cards * 100
    if blocked_pct > 20:
        proposals.append({
            "proposal_id": generate_proposal_id(),
            "title": "Reduce blocked card ratio",
            "rationale": f"{blocked_pct:.1f}% of cards are blocked or escalated",
            "status": "proposed",
            "metrics_before": {
                "blocked_count": blocked_count,
                "total_cards": total_cards,
                "blocked_pct": blocked_pct
            },
            "proposed_change": "Review and resolve blocked cards; improve gate checks",
            "expected_improvement": "Reduce blocked ratio to under 10%",
            "created_at": datetime.now().isoformat(),
            "spec_version": spec_version,
            "source": "auto"
        })

# Check for missing validators
red_count = sum(1 for c in cards.values() if c.get("color") == "RED")
if red_count > 3:
    proposals.append({
        "proposal_id": generate_proposal_id(),
        "title": "Implement missing validators",
        "rationale": f"{red_count} cards are RED (likely due to NOT_RUN validators)",
        "status": "proposed",
        "metrics_before": {
            "red_cards": red_count
        },
        "proposed_change": "Implement real validators in run_validators.py",
        "expected_improvement": "Move cards from RED to GREEN via validation",
        "created_at": datetime.now().isoformat(),
        "spec_version": spec_version,
        "source": "auto"
    })

# Limit to 3 proposals
proposals = proposals[:3]

print(f"Generated {len(proposals)} proposals:")
for p in proposals:
    print(f"  - {p['title']}")
    print(f"    Rationale: {p['rationale']}")
print()

# Write proposals
today = datetime.now().strftime("%Y-%m-%d")
output_file = tower_root / "control" / "kaizen" / "proposals" / f"{today}_proposals.json"

output = {
    "spec_version": spec_version,
    "generated_at": datetime.now().isoformat(),
    "analysis_period_days": days,
    "proposals": proposals
}

tmp_file = str(output_file) + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(output, f, indent=2)
os.replace(tmp_file, str(output_file))

print(f"Proposals saved to: {output_file}")
PYTHON_SCRIPT

echo ""
echo "============================================================"
echo "Kaizen proposal generation complete"
echo "============================================================"
