#!/usr/bin/env bash
#
# Tower Night Runner
# Executes night-safe batch jobs from the night queue.
#
# Usage:
#   night_runner.sh [--dry-run]
#
# Only executes allowlisted "safe batch" commands:
#   - No merges
#   - No destructive operations
#   - Creates run_context + run_summary for each job
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
    if [[ "$path" == /[a-zA-Z]/* ]]; then
        # Convert /c/Users/... to C:/Users/... (keep forward slashes for Python)
        echo "${path:1:1}:${path:2}"
    else
        echo "$path"
    fi
}

NIGHT_QUEUE="$TOWER_ROOT/control/queues/night.json"

# Windows path versions for Python heredocs
TOWER_ROOT_WIN=$(to_win_path "$TOWER_ROOT")

# Parse arguments
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "============================================================"
echo "Tower Night Runner"
echo "Mode: $([ "$DRY_RUN" = true ] && echo 'DRY RUN' || echo 'EXECUTE')"
echo "Time: $(date -Iseconds 2>/dev/null || date)"
echo "============================================================"

# Check if within night window
check_night_window() {
    if [ ! -f "$NIGHT_QUEUE" ]; then
        echo "Night queue not found"
        return 1
    fi

    $PYTHON_CMD << 'PYTHON_SCRIPT'
import json
from datetime import datetime

try:
    import zoneinfo
    tz = zoneinfo.ZoneInfo("Europe/London")
except:
    tz = None

if tz:
    now = datetime.now(tz)
else:
    now = datetime.now()

hour = now.hour

# Night window: 22:00 - 06:00
if hour >= 22 or hour < 6:
    print("IN_WINDOW")
else:
    print("OUTSIDE_WINDOW")
PYTHON_SCRIPT
}

# Check night window
WINDOW_STATUS=$(check_night_window)
if [ "$WINDOW_STATUS" != "IN_WINDOW" ]; then
    echo ""
    echo "Outside night window (22:00 - 06:00 Europe/London)"
    echo "Exiting without running jobs."
    exit 0
fi

# Process queue
echo ""
echo "Processing night queue..."

export TOWER_ROOT_WIN="$TOWER_ROOT_WIN"
export DRY_RUN="$DRY_RUN"
export SPEC_VERSION="$SPEC_VERSION"
$PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

tower_root_env = os.environ.get('TOWER_ROOT_WIN', '')
if not tower_root_env:
    print("ERROR: TOWER_ROOT_WIN environment variable not set", file=sys.stderr)
    sys.exit(1)
tower_root = Path(tower_root_env)
spec_version = os.environ.get('SPEC_VERSION', 'v1.5.7')
dry_run = os.environ.get('DRY_RUN', 'false') == 'true'

night_queue_file = tower_root / "control" / "queues" / "night.json"

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

queue = load_json(night_queue_file)

if not queue.get("enabled", True):
    print("Night queue is disabled")
    exit(0)

jobs = queue.get("jobs", [])
pending_jobs = [j for j in jobs if j.get("status") == "pending"]

print(f"Found {len(pending_jobs)} pending jobs")
print()

for job in pending_jobs:
    job_id = job.get("job_id", "unknown")
    command = job.get("command", "")
    card_id = job.get("card_id")
    safe_batch = job.get("safe_batch", True)

    print(f"Job: {job_id}")
    print(f"  Command: {command}")
    print(f"  Card: {card_id or 'N/A'}")
    print(f"  Safe batch: {safe_batch}")

    if not safe_batch:
        print("  SKIP: Not marked as safe_batch")
        continue

    if dry_run:
        print("  DRY RUN: Would execute")
        continue

    # Validate command against allowlist (stricter version)
    import re

    # Shell metacharacters that could enable injection
    dangerous_chars = [';', '|', '&', '`', '$', '(', ')', '<', '>', '\n']
    if any(c in command for c in dangerous_chars):
        print(f"  BLOCKED: Command contains shell metacharacters")
        job["status"] = "blocked"
        job["exit_code"] = -2
        job["completed_at"] = datetime.now().isoformat()
        print()
        continue

    # Blocklist patterns (dangerous operations)
    blocklist_patterns = [
        r'git\s+merge', r'git\s+push', r'rm\s+-rf', r'dd\s+if=',
        r'mkfs\.', r'format\s+', r'curl\s+', r'wget\s+',
        r'chmod\s+', r'chown\s+', r'sudo\s+', r'su\s+',
        r'eval\s+', r'exec\s+',
        r'-c\s+["\']',  # Block -c flag with code strings (python -c, bash -c)
        r'__import__', r'subprocess', r'os\.system', r'os\.popen'  # Python code injection
    ]

    # Allowlist: only specific script patterns (no arbitrary code execution)
    # Note: (?!.*\.\.) negative lookahead prevents path traversal
    allowlist_patterns = [
        r'^pytest\s+(?!.*\.\./)[\w\./]+',          # pytest with specific test paths
        r'^npm\s+test$',                            # npm test (exact match)
        r'^npm\s+run\s+build$',                     # npm run build (exact match)
        r'^make\s+test$',                           # make test (exact match)
        r'^cargo\s+test$',                          # cargo test (exact match)
        r'^python3?\s+(?!.*\.\./)[\w\./]+\.py\b',  # python with specific .py file (no ..)
        r'^bash\s+(?!.*\.\./)[\w\./]+\.sh\b',      # bash with specific .sh file (no ..)
    ]

    is_blocked = any(re.search(p, command) for p in blocklist_patterns)
    is_allowed = any(re.search(p, command) for p in allowlist_patterns)

    if is_blocked:
        print(f"  BLOCKED: Command matches blocklist pattern")
        job["status"] = "blocked"
        job["exit_code"] = -2
        job["completed_at"] = datetime.now().isoformat()
        print()
        continue

    if not is_allowed:
        print(f"  BLOCKED: Command not in allowlist (only safe script patterns allowed)")
        job["status"] = "blocked"
        job["exit_code"] = -2
        job["completed_at"] = datetime.now().isoformat()
        print()
        continue

    # Validate script paths don't traverse outside tower_root
    import shlex
    cmd_parts = shlex.split(command)
    path_blocked = False
    for part in cmd_parts:
        if part.endswith('.py') or part.endswith('.sh'):
            # Early rejection: block absolute paths and path traversal patterns
            if Path(part).is_absolute():
                print(f"  BLOCKED: Absolute path not allowed: {part}")
                path_blocked = True
                break
            if '..' in part:
                print(f"  BLOCKED: Path traversal (..) not allowed: {part}")
                path_blocked = True
                break
            # Resolve relative to tower_root and verify it stays within
            resolved = (tower_root / part).resolve()
            try:
                resolved.relative_to(tower_root.resolve())
            except ValueError:
                print(f"  BLOCKED: Script path outside tower root: {part}")
                path_blocked = True
                break

    if path_blocked:
        job["status"] = "blocked"
        job["exit_code"] = -3
        job["completed_at"] = datetime.now().isoformat()
        print()
        continue  # Skip this job entirely

    # Execute job with shell=False for safety
    print("  Executing...")
    job["status"] = "running"
    job["started_at"] = datetime.now().isoformat()

    try:
        result = subprocess.run(
            cmd_parts,  # Use parsed arguments, not raw string
            shell=False,  # Safer: no shell interpretation
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour max
            cwd=str(tower_root)  # Run from tower root
        )
        exit_code = result.returncode
        job["status"] = "completed" if exit_code == 0 else "failed"
        job["exit_code"] = exit_code
        print(f"  Exit code: {exit_code}")
    except subprocess.TimeoutExpired:
        job["status"] = "failed"
        job["exit_code"] = -1
        print("  TIMEOUT")
    except Exception as e:
        job["status"] = "failed"
        job["exit_code"] = -1
        print(f"  ERROR: {e}")

    job["completed_at"] = datetime.now().isoformat()
    print()

# Update queue file
queue["last_updated"] = datetime.now().isoformat()
tmp_file = str(night_queue_file) + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(queue, f, indent=2)
os.replace(tmp_file, str(night_queue_file))

print("Queue updated")
PYTHON_SCRIPT

echo ""
echo "============================================================"
echo "Night runner complete"
echo "============================================================"
