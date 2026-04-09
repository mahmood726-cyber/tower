# Runbook: Drift Incident Response

## Trigger

Alert from `tower/control/alerts/drift_alerts.json` or watchdog reporting state drift.

## Severity

- **S2** if affecting active cards
- **S3** if limited to historical data

## Immediate Actions

1. **Assess scope**
   ```bash
   cat tower/control/alerts/drift_alerts.json
   bash tower/scripts/tower_watchdog.sh
   ```

2. **Pause affected work**
   - Do not merge any cards in affected streams
   - Note which cards are currently ACTIVE

3. **Capture state**
   ```bash
   cp tower/control/status.json "tower/control/backups/status_$(date +%Y%m%d%H%M%S)_drift.json"
   bash tower/scripts/tower_dashboard.sh
   ```

## Investigation

1. **Identify drift source**
   - Compare status.json with git history
   - Check recent manual edits
   - Review artifact timestamps

2. **Determine drift extent**
   - Which cards affected?
   - Which fields drifted?
   - When did drift start?

## Resolution

### Option A: Simple reconciliation

If drift is minor and source is clear:

```bash
# Fix the drifted values manually
# Validate
bash tower/scripts/validate_all.sh
```

### Option B: Restore from backup

If drift is extensive:

```bash
bash tower/scripts/recover_control_state.sh --backup <backup_file>
bash tower/scripts/validate_all.sh
```

### Option C: Full reconciliation

If source unknown:

1. Export current state
2. Rebuild from artifacts
3. Validate against git history
4. Apply fixes

## Post-Incident

1. **Clear alerts**
   - Remove resolved alerts from drift_alerts.json

2. **Document**
   - Create postmortem in `tower/addons/resilience/postmortems/`

3. **Prevent recurrence**
   - Consider Kaizen proposal if systemic

## Escalation

Escalate to S1 if:
- Drift affects merged cards
- Cannot determine accurate state
- Multiple simultaneous drifts
