# Event Ledger Add-on

Canonical append-only event log with file locking for Tower operations.

## Overview

The Event Ledger provides an immutable audit trail of all Tower operations. Every state change, validation, merge, and system event is recorded with timestamps and context.

## Features

- **Append-only**: Events can only be added, never modified or deleted
- **File locking**: Prevents concurrent write corruption
- **Structured format**: JSON Lines (JSONL) for easy parsing
- **Tamper detection**: Optional hash chaining
- **Query support**: Filter by event type, card, time range

## Quick Start

```bash
# Log an event from bash
bash tower/addons/ledger/log_event.sh "card.state_change" "CARD-042" '{"from": "ACTIVE", "to": "GREEN"}'

# Log from Python
python tower/addons/ledger/event_logger.py log --type "validation.pass" --card "CARD-042"

# Query events
python tower/addons/ledger/event_logger.py query --type "card.*" --since "2025-01-17"

# Verify ledger integrity
python tower/addons/ledger/event_logger.py verify
```

## Event Schema

Each event is a JSON object with these fields:

```json
{
  "id": "evt_20250117_103045_abc123",
  "timestamp": "2025-01-17T10:30:45.123456Z",
  "type": "card.state_change",
  "card_id": "CARD-042",
  "actor": "tower_gatecheck.sh",
  "data": {
    "from": "ACTIVE",
    "to": "GREEN"
  },
  "prev_hash": "sha256:abc123...",
  "hash": "sha256:def456..."
}
```

### Required Fields

| Field | Description |
|-------|-------------|
| `id` | Unique event identifier |
| `timestamp` | ISO 8601 timestamp with microseconds |
| `type` | Event type (hierarchical, dot-separated) |

### Optional Fields

| Field | Description |
|-------|-------------|
| `card_id` | Associated card if applicable |
| `actor` | Script or user that triggered the event |
| `data` | Arbitrary JSON payload |
| `prev_hash` | Hash of previous event (for chaining) |
| `hash` | Hash of this event |

## Event Types

### Card Events

| Type | Description |
|------|-------------|
| `card.created` | New card added to backlog |
| `card.state_change` | Card transitioned states |
| `card.escalated` | Card escalated to human |
| `card.archived` | Card moved to archive |

### Validation Events

| Type | Description |
|------|-------------|
| `validation.started` | Validation run began |
| `validation.pass` | Validation succeeded |
| `validation.fail` | Validation failed |
| `validation.skipped` | Validation skipped |

### Merge Events

| Type | Description |
|------|-------------|
| `merge.requested` | Merge requested |
| `merge.approved` | Merge approved |
| `merge.completed` | Merge to gold completed |
| `merge.rejected` | Merge rejected |
| `merge.rolled_back` | Merge rolled back |

### System Events

| Type | Description |
|------|-------------|
| `system.freeze_activated` | Merge freeze enabled |
| `system.freeze_cleared` | Merge freeze cleared |
| `system.backup_created` | Control backup created |
| `system.quota_warning` | Quota threshold reached |

### SLO Events

| Type | Description |
|------|-------------|
| `slo.computed` | SLO metrics computed |
| `slo.breached` | SLO threshold breached |
| `slo.budget_depleted` | Error budget exhausted |

## Files

| File | Description |
|------|-------------|
| `tower/control/event_ledger.jsonl` | Main event log |
| `tower/control/event_ledger.lock` | Lock file for writes |
| `tower/control/backups/event_ledger_*.jsonl` | Rotated backups |

## Python API

```python
from event_logger import EventLogger

logger = EventLogger("tower/control/event_ledger.jsonl")

# Log an event
logger.log(
    event_type="card.state_change",
    card_id="CARD-042",
    actor="my_script.py",
    data={"from": "ACTIVE", "to": "GREEN"}
)

# Query events
events = logger.query(
    event_type="card.*",
    card_id="CARD-042",
    since="2025-01-17",
    until="2025-01-18"
)

# Verify integrity
is_valid, errors = logger.verify()
```

## Bash API

```bash
# Simple event
log_event.sh <type> [card_id] [data_json]

# Examples
log_event.sh "card.created" "CARD-043" '{"title": "New feature"}'
log_event.sh "system.backup_created" "" '{"file": "status_backup.json"}'
log_event.sh "validation.pass" "CARD-042"
```

## Integration

### With Tower Scripts

Add to any Tower script:

```bash
# At the top
source tower/addons/ledger/log_event.sh

# Log events
log_event "card.state_change" "$CARD_ID" "{\"from\": \"$OLD_STATE\", \"to\": \"$NEW_STATE\"}"
```

### With Python Wrapper

```python
import sys
sys.path.append("tower/addons/ledger")
from event_logger import EventLogger

logger = EventLogger()
logger.log("my.event", data={"key": "value"})
```

## Rotation & Retention

By default, the ledger rotates when it exceeds 10MB:

```bash
# Manual rotation
python tower/addons/ledger/event_logger.py rotate

# Rotation happens automatically on log if size > 10MB
```

Rotated files are named: `event_ledger_YYYYMMDD_HHMMSS.jsonl`

## Verification

The ledger supports hash chaining for tamper detection:

```bash
# Verify entire ledger
python tower/addons/ledger/event_logger.py verify

# Output
Verifying ledger integrity...
  Events checked: 1247
  Hash chain: VALID
  First event: 2025-01-01T00:00:00Z
  Last event: 2025-01-17T10:30:00Z
  Status: OK
```

If tampering is detected:

```
Verifying ledger integrity...
  Events checked: 1247
  Hash chain: BROKEN at event evt_20250115_...
  Error: Hash mismatch at line 892
  Status: COMPROMISED
```

## Best Practices

1. **Always log state changes** - Every card state transition should be logged
2. **Include context** - Add relevant data to help with debugging
3. **Use consistent types** - Follow the hierarchical naming convention
4. **Don't log secrets** - Never include API keys, tokens, or credentials
5. **Verify periodically** - Run verification in CI/CD or nightly runner

## Troubleshooting

### Lock File Stale

If writes fail due to stale lock:

```bash
# Check lock age
ls -la tower/control/event_ledger.lock

# Remove if stale (> 5 minutes old)
find tower/control -name "event_ledger.lock" -mmin +5 -delete
```

### Corrupted Event

If a line is malformed JSON:

```bash
# Find the bad line
python -c "import json; [json.loads(l) for l in open('tower/control/event_ledger.jsonl')]"

# Will show the line number of the error
```

### Large Ledger

If the ledger is too large:

```bash
# Force rotation
python tower/addons/ledger/event_logger.py rotate --force

# Archive old backups
tar -czf event_ledger_archive.tar.gz tower/control/backups/event_ledger_*.jsonl
rm tower/control/backups/event_ledger_*.jsonl
```
