#!/usr/bin/env bash
#
# Tower Gatecheck Script
# Evaluates gates for cards and updates status.json
#
# Usage:
#   tower_gatecheck.sh [--card CARD-XXX]  # Check specific card
#   tower_gatecheck.sh                     # Check all active cards
#
# Gate evaluation:
#   GREEN: gates PASS + validators PASS + proofpack exists
#   YELLOW: partial pass (some gates pass)
#   RED: any FAIL or ESCALATED
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

# Convert Git Bash path to Windows path for Python (using forward slashes)
to_win_path() {
    local path="$1"
    # Git Bash: /c/Users/... -> C:/Users/...
    if [[ "$path" == /[a-zA-Z]/* ]]; then
        echo "${path:1:1}:${path:2}"
    # Cygwin: /cygdrive/c/Users/... -> C:/Users/...
    elif [[ "$path" == /cygdrive/[a-zA-Z]/* ]]; then
        echo "${path:10:1}:${path:11}"
    else
        echo "$path"
    fi
}

STATUS_FILE="$TOWER_ROOT/control/status.json"
BACKUP_DIR="$TOWER_ROOT/control/backups"

# Windows path versions for Python heredocs
STATUS_FILE_WIN=$(to_win_path "$STATUS_FILE")

# Parse arguments
CARD_ID=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --card)
            CARD_ID="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate CARD_ID format if provided (prevent injection)
if [ -n "$CARD_ID" ]; then
    if ! echo "$CARD_ID" | grep -qE '^CARD-[0-9]+$'; then
        echo "ERROR: --card must match CARD-NNN format (got: $CARD_ID)"
        exit 1
    fi
fi

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Create backup of current status
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
if [ -f "$STATUS_FILE" ]; then
    cp "$STATUS_FILE" "$BACKUP_DIR/status_${TIMESTAMP}.json"
fi

echo "============================================================"
echo "Tower Gatecheck"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "Card: ${CARD_ID:-all active}"
echo "============================================================"

# Atomic JSON update function
atomic_json_write() {
    local file="$1"
    local content="$2"
    local tmp_file="${file}.tmp.$$"

    echo "$content" > "$tmp_file"
    sync "$tmp_file" 2>/dev/null || true
    mv "$tmp_file" "$file"
}

# Evaluate gates for a card (TruthCert-style with severity levels)
evaluate_card_gates() {
    local card_id="$1"
    local today=$(date +%Y-%m-%d)
    local card_artifacts="$TOWER_ROOT/artifacts/$today/$card_id"
    local proofpacks="$TOWER_ROOT/proofpacks/$today/$card_id"

    # Gate statuses
    local tests_status="NOT_RUN"
    local validators_status="NOT_RUN"
    local proofpack_status="NOT_RUN"

    # Severity levels: P0=Block, P1=Warn, P2=Info
    # tests = P0 (must pass to merge)
    # validators = P0 (must pass to merge)
    # proofpack = P1 (caps badge if missing)
    local tests_severity="P0"
    local validators_severity="P0"
    local proofpack_severity="P1"

    local color="RED"
    local assurance="none"
    local p0_passed="true"
    local p1_passed="true"

    # Check for test results in artifacts
    if [ -d "$card_artifacts" ]; then
        local has_pass=false
        local has_fail=false

        for summary in "$card_artifacts"/run_*/run_summary.json; do
            if [ -f "$summary" ]; then
                local summary_win=$(to_win_path "$summary")
                exit_code=$(_GC_SUMMARY="$summary_win" $PYTHON_CMD -c "import json, os; print(json.load(open(os.environ['_GC_SUMMARY'])).get('exit_code', -1))" 2>/dev/null || echo "-1")
                if [ "$exit_code" = "0" ]; then
                    has_pass=true
                else
                    has_fail=true
                fi
            fi
        done

        if $has_pass && ! $has_fail; then
            tests_status="PASS"
        elif $has_fail; then
            tests_status="FAIL"
            p0_passed="false"
        fi
    fi

    # Check for validator report
    for report in "$card_artifacts"/*/validator_report.json; do
        if [ -f "$report" ]; then
            local report_win=$(to_win_path "$report")
            overall=$(_GC_REPORT="$report_win" $PYTHON_CMD -c "import json, os; print(json.load(open(os.environ['_GC_REPORT'])).get('overall_status', 'NOT_RUN'))" 2>/dev/null || echo "NOT_RUN")
            validators_status="$overall"
            if [ "$validators_status" = "FAIL" ] || [ "$validators_status" = "BLOCKED" ]; then
                p0_passed="false"
            fi
            break
        fi
    done

    # Check for proofpack
    if [ -d "$proofpacks" ] && [ -f "$proofpacks/manifest.json" ]; then
        proofpack_status="PASS"
    else
        p1_passed="false"
    fi

    # Compute assurance level (TruthCert ladder)
    # None:   P0 failures (blocked)
    # Bronze: P0 pass but gates NOT_RUN (early stage)
    # Silver: P0 pass + gates actually run and pass (ready for proofpack)
    # Gold:   Silver + proofpack exists

    local gates_actually_run="false"
    if [ "$tests_status" = "PASS" ] || [ "$validators_status" = "PASS" ]; then
        gates_actually_run="true"
    fi

    if [ "$p0_passed" = "false" ]; then
        assurance="none"
        color="RED"
    elif [ "$proofpack_status" = "PASS" ] && [ "$gates_actually_run" = "true" ]; then
        # Gold: gates run and pass + proofpack exists
        assurance="gold"
        color="GREEN"
    elif [ "$gates_actually_run" = "true" ]; then
        # Silver: gates run and pass but no proofpack yet
        assurance="silver"
        color="YELLOW"
    else
        # Bronze: no P0 failures but gates haven't run yet
        assurance="bronze"
        color="YELLOW"
    fi

    echo "  Card: $card_id" >&2
    echo "    Tests:      $tests_status (${tests_severity})" >&2
    echo "    Validators: $validators_status (${validators_severity})" >&2
    echo "    Proofpack:  $proofpack_status (${proofpack_severity})" >&2
    echo "    Assurance:  $assurance" >&2
    echo "    Color:      $color" >&2

    # Return as JSON fragment with TruthCert fields
    cat << EOF
{
  "card_id": "$card_id",
  "gates": {
    "tests": {"status": "$tests_status", "severity": "$tests_severity"},
    "validators": {"status": "$validators_status", "severity": "$validators_severity"},
    "proofpack": {"status": "$proofpack_status", "severity": "$proofpack_severity"}
  },
  "p0_passed": $p0_passed,
  "p1_passed": $p1_passed,
  "assurance": "$assurance",
  "color": "$color",
  "updated_at": "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)"
}
EOF
}

# Process cards
if [ -n "$CARD_ID" ]; then
    # Single card
    echo ""
    result=$(evaluate_card_gates "$CARD_ID")
    echo ""

    # Update status.json (pass data via temp file to avoid shell injection)
    if [ -f "$STATUS_FILE" ]; then
        RESULT_TMP="$TOWER_ROOT/control/.gatecheck_result.$$.json.tmp"
        echo "$result" > "$RESULT_TMP"
        RESULT_TMP_WIN=$(to_win_path "$RESULT_TMP")

        _GC_STATUS_FILE="$STATUS_FILE_WIN" \
        _GC_CARD_ID="$CARD_ID" \
        _GC_RESULT_FILE="$RESULT_TMP_WIN" \
        $PYTHON_CMD << 'PYEOF'
import json
import os
import sys
from datetime import datetime

status_file = os.environ.get("_GC_STATUS_FILE", "")
card_id = os.environ.get("_GC_CARD_ID", "")
result_file = os.environ.get("_GC_RESULT_FILE", "")

if not status_file or not card_id or not result_file:
    print("ERROR: missing environment variables", file=sys.stderr)
    sys.exit(1)

try:
    with open(result_file, 'r') as f:
        result = json.load(f)
finally:
    # Always clean up temp file
    try:
        os.remove(result_file)
    except:
        pass

with open(status_file, 'r') as f:
    status = json.load(f)

# cards is an array of objects, not a dict
cards = status.get("cards", [])
if not isinstance(cards, list):
    cards = list(cards.values()) if isinstance(cards, dict) else []

# Find existing card or create new entry
card_entry = None
card_index = None
for i, c in enumerate(cards):
    if c.get("card_id") == card_id:
        card_entry = c
        card_index = i
        break

is_new_card = False
if card_entry is None:
    card_entry = {
        "card_id": card_id,
        "state": "REVIEW",
        "stream": "apps",
        "window": None,
        "run_ids": []
    }
    cards.append(card_entry)
    is_new_card = True

# Detect drift before updating (TruthCert drift ledger)
drift_events = []
if not is_new_card:
    old_gates = card_entry.get("gates", {})
    new_gates = result["gates"]
    old_color = card_entry.get("color", "RED")
    new_color = result["color"]
    old_assurance = card_entry.get("assurance", "none")
    new_assurance = result.get("assurance", "none")

    # Check gate status changes
    for gate_name in ["tests", "validators", "proofpack"]:
        old_status = old_gates.get(gate_name, {})
        new_status = new_gates.get(gate_name, {})
        # Handle both old format (string) and new format (dict)
        old_val = old_status.get("status") if isinstance(old_status, dict) else old_status
        new_val = new_status.get("status") if isinstance(new_status, dict) else new_status
        if old_val and new_val and old_val != new_val:
            # Regression (PASS -> FAIL) is P0, improvement is P2
            if old_val == "PASS" and new_val == "FAIL":
                severity = "P0"
            elif old_val == "FAIL" and new_val == "PASS":
                severity = "P2"
            else:
                severity = "P1"
            drift_events.append({
                "drift_type": "status_change",
                "card_id": card_id,
                "field": f"gates.{gate_name}",
                "old_value": old_val,
                "new_value": new_val,
                "timestamp": datetime.now().isoformat(),
                "severity": severity,
                "adjudicated": False
            })

    # Check color regression
    color_order = {"GREEN": 2, "YELLOW": 1, "RED": 0}
    if old_color != new_color:
        if color_order.get(new_color, 0) < color_order.get(old_color, 0):
            drift_events.append({
                "drift_type": "status_change",
                "card_id": card_id,
                "field": "color",
                "old_value": old_color,
                "new_value": new_color,
                "timestamp": datetime.now().isoformat(),
                "severity": "P1",
                "adjudicated": False
            })

# Update with TruthCert fields
card_entry["gates"] = result["gates"]
card_entry["color"] = result["color"]
card_entry["assurance"] = result.get("assurance", "none")
card_entry["p0_passed"] = result.get("p0_passed", False)
card_entry["p1_passed"] = result.get("p1_passed", False)
card_entry["updated_at"] = result["updated_at"]

# State transition: when assurance reaches "gold", set state to "GOLD" for merge eligibility
if card_entry["assurance"] == "gold" and card_entry.get("state") not in ("GOLD", "MERGED"):
    old_state = card_entry.get("state", "DRAFT")
    card_entry["state"] = "GOLD"
    drift_events.append({
        "drift_type": "state_promotion",
        "card_id": card_id,
        "field": "state",
        "old_value": old_state,
        "new_value": "GOLD",
        "timestamp": datetime.now().isoformat(),
        "severity": "P2",  # Info: state promotion is expected
        "adjudicated": True,
        "adjudication_reason": "auto: assurance=gold triggers state=GOLD"
    })

# State demotion: when assurance drops below gold, demote state from GOLD back to REVIEW
# (Don't demote if already MERGED - that's final)
if card_entry["assurance"] != "gold" and card_entry.get("state") == "GOLD":
    old_state = card_entry["state"]
    card_entry["state"] = "REVIEW"
    drift_events.append({
        "drift_type": "state_demotion",
        "card_id": card_id,
        "field": "state",
        "old_value": old_state,
        "new_value": "REVIEW",
        "timestamp": datetime.now().isoformat(),
        "severity": "P1",  # Warning: assurance dropped, state demoted
        "adjudicated": False,
        "adjudication_reason": None
    })

status["cards"] = cards
status["last_updated"] = datetime.now().isoformat()

# Atomic write
tmp_file = status_file + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(status, f, indent=2)

os.replace(tmp_file, status_file)
print(f"Updated status for {card_id}")

# Record drift events to ledger
if drift_events:
    import pathlib
    ledger_path = pathlib.Path(status_file).parent / "drift_ledger.json"
    ledger_data = {"spec_version": "v1.0.0", "events": []}
    if ledger_path.exists():
        try:
            with open(ledger_path) as f:
                ledger_data = json.load(f)
        except:
            pass
    ledger_data["events"].extend(drift_events)
    ledger_data["updated_at"] = datetime.now().isoformat()
    tmp_ledger = str(ledger_path) + ".tmp"
    with open(tmp_ledger, 'w') as f:
        json.dump(ledger_data, f, indent=2)
    os.replace(tmp_ledger, str(ledger_path))
    print(f"Recorded {len(drift_events)} drift event(s)")
PYEOF
    fi
else
    # All cards in status
    echo ""
    if [ -f "$STATUS_FILE" ]; then
        cards=$(_GC_STATUS_FILE="$STATUS_FILE_WIN" $PYTHON_CMD -c "
import json, os
with open(os.environ['_GC_STATUS_FILE']) as f:
    d = json.load(f)
c = d.get('cards', [])
if isinstance(c, list):
    print(' '.join(x.get('card_id','') for x in c if x.get('state','') not in ('MERGED','ARCHIVED')))
elif isinstance(c, dict):
    print(' '.join(c.keys()))
" 2>/dev/null || echo "")

        if [ -z "$cards" ]; then
            echo "No cards in status.json"
        else
            for card in $cards; do
                result=$(evaluate_card_gates "$card")
                echo ""

                # Update status.json for this card (same logic as single-card mode)
                # Use card ID + PID + timestamp for unique temp file
                RESULT_TMP="$TOWER_ROOT/control/.gatecheck_result.${card}.$$.$(date +%s%N 2>/dev/null || date +%s).json.tmp"
                echo "$result" > "$RESULT_TMP"
                RESULT_TMP_WIN=$(to_win_path "$RESULT_TMP")

                _GC_STATUS_FILE="$STATUS_FILE_WIN" \
                _GC_CARD_ID="$card" \
                _GC_RESULT_FILE="$RESULT_TMP_WIN" \
                $PYTHON_CMD << 'PYEOF'
import json
import os
import sys
from datetime import datetime

status_file = os.environ.get("_GC_STATUS_FILE", "")
card_id = os.environ.get("_GC_CARD_ID", "")
result_file = os.environ.get("_GC_RESULT_FILE", "")

if not status_file or not card_id or not result_file:
    print(f"ERROR: Missing environment variables for {card_id}", file=sys.stderr)
    sys.exit(1)

try:
    with open(result_file, 'r') as f:
        result = json.load(f)
except Exception as e:
    print(f"ERROR: Could not read result file for {card_id}: {e}", file=sys.stderr)
    sys.exit(1)
finally:
    # Always clean up temp file
    try:
        os.remove(result_file)
    except:
        pass

try:
    with open(status_file, 'r') as f:
        status = json.load(f)
except json.JSONDecodeError as e:
    print(f"ERROR: status.json is corrupted: {e}", file=sys.stderr)
    sys.exit(1)

cards = status.get("cards", [])
if not isinstance(cards, list):
    cards = list(cards.values()) if isinstance(cards, dict) else []

drift_events = []

for c in cards:
    if c.get("card_id") == card_id:
        # Detect drift before updating
        old_gates = c.get("gates", {})
        new_gates = result["gates"]
        old_color = c.get("color", "RED")
        new_color = result["color"]

        for gate_name in ["tests", "validators", "proofpack"]:
            old_status = old_gates.get(gate_name, {})
            new_status = new_gates.get(gate_name, {})
            old_val = old_status.get("status") if isinstance(old_status, dict) else old_status
            new_val = new_status.get("status") if isinstance(new_status, dict) else new_status
            if old_val and new_val and old_val != new_val:
                severity = "P0" if (old_val == "PASS" and new_val == "FAIL") else "P1"
                drift_events.append({
                    "drift_type": "status_change",
                    "card_id": card_id,
                    "field": f"gates.{gate_name}",
                    "old_value": old_val,
                    "new_value": new_val,
                    "timestamp": datetime.now().isoformat(),
                    "severity": severity,
                    "adjudicated": False
                })

        # Update with TruthCert fields
        c["gates"] = result["gates"]
        c["color"] = result["color"]
        c["assurance"] = result.get("assurance", "none")
        c["p0_passed"] = result.get("p0_passed", False)
        c["p1_passed"] = result.get("p1_passed", False)
        c["updated_at"] = result["updated_at"]

        # State transition: when assurance reaches "gold", set state to "GOLD"
        if c["assurance"] == "gold" and c.get("state") not in ("GOLD", "MERGED"):
            old_state = c.get("state", "DRAFT")
            c["state"] = "GOLD"
            drift_events.append({
                "drift_type": "state_promotion",
                "card_id": card_id,
                "field": "state",
                "old_value": old_state,
                "new_value": "GOLD",
                "timestamp": datetime.now().isoformat(),
                "severity": "P2",
                "adjudicated": True,
                "adjudication_reason": "auto: assurance=gold triggers state=GOLD"
            })

        # State demotion: when assurance drops below gold, demote from GOLD
        if c["assurance"] != "gold" and c.get("state") == "GOLD":
            old_state = c["state"]
            c["state"] = "REVIEW"
            drift_events.append({
                "drift_type": "state_demotion",
                "card_id": card_id,
                "field": "state",
                "old_value": old_state,
                "new_value": "REVIEW",
                "timestamp": datetime.now().isoformat(),
                "severity": "P1",
                "adjudicated": False,
                "adjudication_reason": None
            })
        break

status["cards"] = cards
status["last_updated"] = datetime.now().isoformat()

tmp_file = status_file + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(status, f, indent=2)
os.replace(tmp_file, status_file)

# Record drift events
if drift_events:
    import pathlib
    ledger_path = pathlib.Path(status_file).parent / "drift_ledger.json"
    ledger_data = {"spec_version": "v1.0.0", "events": []}
    if ledger_path.exists():
        try:
            with open(ledger_path) as f:
                ledger_data = json.load(f)
        except:
            pass
    ledger_data["events"].extend(drift_events)
    ledger_data["updated_at"] = datetime.now().isoformat()
    tmp_ledger = str(ledger_path) + ".tmp"
    with open(tmp_ledger, 'w') as f:
        json.dump(ledger_data, f, indent=2)
    os.replace(tmp_ledger, str(ledger_path))
PYEOF
            done
            echo "Status updated for all cards"
        fi
    else
        echo "status.json not found"
    fi
fi

echo "============================================================"
echo "Gatecheck complete"
echo "Backup saved: $BACKUP_DIR/status_${TIMESTAMP}.json"
echo "============================================================"
