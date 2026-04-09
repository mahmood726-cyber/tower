# Runbook: Control File Corruption

## Trigger

- Validation fails with parse errors
- Control files contain invalid JSON
- Unexpected null or missing fields

## Severity

- **S1** if status.json corrupted
- **S2** if other control files affected
- **S3** if limited to non-critical files

## Immediate Actions

1. **Stop all operations**
   ```bash
   echo '{"active": true, "reason": "Control corruption"}' > tower/control/merge_freeze.json
   ```

2. **Assess damage**
   ```bash
   # Try to parse each control file
   for f in tower/control/*.json; do
     echo "Checking $f..."
     jq . "$f" > /dev/null 2>&1 || echo "  CORRUPTED: $f"
   done
   ```

3. **Find latest good backup**
   ```bash
   ls -la tower/control/backups/
   ```

## Investigation

1. **Identify corruption source**
   - Interrupted write?
   - Manual edit error?
   - Disk issue?
   - Git conflict?

2. **Determine extent**
   - Which files affected?
   - Which fields corrupted?
   - Any data loss?

## Recovery Options

### Option A: Restore from backup

```bash
bash tower/scripts/recover_control_state.sh --backup tower/control/backups/status_YYYYMMDD.json
bash tower/scripts/validate_all.sh
```

### Option B: Repair manually

If corruption is minor (e.g., trailing comma):
1. Identify the syntax error
2. Fix with text editor
3. Validate with jq

### Option C: Rebuild from artifacts

If no recent backup:
1. Initialize fresh control files
2. Reconstruct state from artifacts
3. Reconcile with git history

## Validation After Recovery

```bash
# Full validation
bash tower/scripts/validate_all.sh

# Check all control files
for f in tower/control/*.json; do
  echo "Validating $f..."
  jq . "$f" > /dev/null
done

# Regenerate dashboard
bash tower/scripts/tower_dashboard.sh
```

## Post-Incident

1. **Document the incident**
   - What was corrupted?
   - How was it recovered?
   - Any data loss?

2. **Prevent recurrence**
   - Review atomic write patterns
   - Check disk health
   - Consider more frequent backups

3. **Clear freeze**
   ```bash
   rm tower/control/merge_freeze.json
   ```

## Prevention

- Always use atomic writes (temp + fsync + rename)
- Backup before manual edits
- Regular validation runs
- Git-tracked control files where appropriate

## Escalation

Escalate to S1 if:
- Cannot restore from backup
- Data loss confirmed
- Corruption source unknown
