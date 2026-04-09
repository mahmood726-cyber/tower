# Tower Ops Runbook v1.5.5

**Purpose:** Keep Tower shipping safely with minimal supervision.
**Source of truth:** `tower/control/*.json` + `tower/artifacts/**` + `tower/proofpacks/**` (not external dashboards/tools).
**Golden rule:** If something goes weird, **stop the bleeding -> capture artifacts -> recover state -> resume.**

## 0) Quick Locations (Memorize These)

| What | Path |
|------|------|
| Dashboard | `tower/control/dashboard.html` |
| Status | `tower/control/status.json` |
| Backlog | `tower/control/backlog.json` |
| Quota | `tower/control/quota.json` |
| Alerts | `tower/control/alerts/*.json` |
| Incidents | `tower/control/incidents/` |
| Artifacts | `tower/artifacts/YYYY-MM-DD/<CARD>/...` |
| Proofpacks | `tower/proofpacks/YYYY-MM-DD/<CARD>/` |
| Backups | `tower/control/backups/` |
| SLO Status | `tower/control/slo_status.json` |

## 1) Daily "Start-of-Day" (5 Minutes)

Run these in repo root:

```bash
bash tower/scripts/validate_all.sh
bash tower/scripts/tower_gatecheck.sh
bash tower/scripts/tower_dashboard.sh
```

Check dashboard.html for:
- [ ] Any ESCALATED cards? -> Investigate first
- [ ] Any BLOCKED cards? -> Check blockers
- [ ] Quota status? -> Sufficient for planned work?
- [ ] SLO status? -> Any WARN or BREACH?

If all green: proceed with normal work.

## 2) Daily "End-of-Day" (3 Minutes)

```bash
bash tower/scripts/tower_dashboard.sh
bash tower/scripts/tower_watchdog.sh
```

Check:
- [ ] Any new alerts? -> Acknowledge or fix
- [ ] Cards progressed? -> Should see state changes
- [ ] Backups fresh? -> Should be <24h old

## 3) Common Operations

### Start New Card

```bash
# 1. Create card worktree
cd tower/worktrees
git worktree add CARD-XXX -b CARD-XXX

# 2. Add to backlog
# Edit tower/control/backlog.json

# 3. Validate
bash tower/scripts/validate_all.sh
```

### Move Card to ACTIVE

```bash
# 1. Update status.json - set state: "ACTIVE"
# 2. Run gatecheck
bash tower/scripts/tower_gatecheck.sh
```

### Submit Card for Review

```bash
# 1. Run validators
bash tower/scripts/run_validators.py --card CARD-XXX

# 2. Build proofpack
bash tower/scripts/tower_proofpack.sh --card CARD-XXX

# 3. Update state to REVIEW_PENDING
```

### Merge Card to Gold

```bash
# 1. Verify card is GREEN
# 2. Run merge (dry run first)
bash tower/scripts/merge_gold.sh --card CARD-XXX
bash tower/scripts/merge_gold.sh --card CARD-XXX --do-merge
```

### Rollback a Card

```bash
# 1. Identify commit to revert
git log --oneline gold -10

# 2. Revert
git revert <commit-sha>

# 3. Update status to ROLLED_BACK
# 4. Create incident report
```

## 4) Incident Response

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| S1 | Production broken, data at risk | Immediate |
| S2 | Major feature broken | <2 hours |
| S3 | Minor issue, workaround exists | <24 hours |
| S4 | Cosmetic, documentation | Next sprint |

### Response Steps

1. **Stop the Bleeding**
   ```bash
   # Freeze merges if needed
   echo '{"active": true, "reason": "Incident in progress"}' > tower/control/merge_freeze.json
   ```

2. **Capture State**
   ```bash
   # Backup current state
   cp tower/control/status.json "tower/control/backups/status_$(date +%Y%m%d%H%M%S).json"

   # Capture artifacts
   bash tower/scripts/tower_dashboard.sh
   ```

3. **Investigate**
   - Check `tower/control/alerts/*.json`
   - Check recent artifacts
   - Check git history

4. **Fix**
   - Apply minimal fix
   - Validate fix works
   - Document in incident report

5. **Resume**
   ```bash
   # Clear freeze
   rm tower/control/merge_freeze.json

   # Validate system
   bash tower/scripts/validate_all.sh
   ```

## 5) Troubleshooting

### "Validation Failed"

```bash
# Check which files failed
bash tower/scripts/validate_all.sh 2>&1 | grep -i fail

# Common fixes:
# - JSON syntax error: Use jq to validate
jq . tower/control/status.json

# - Schema mismatch: Check spec_version
grep spec_version tower/control/*.json
```

### "Gatecheck Failed"

```bash
# Check gate output
bash tower/scripts/tower_gatecheck.sh 2>&1 | tail -50

# Common causes:
# - Card not in correct state
# - Missing required fields
# - Quota exceeded
```

### "Card Stuck in State"

```bash
# Check card details
jq '.cards["CARD-XXX"]' tower/control/status.json

# Common causes:
# - Waiting for dependency
# - Blocked by reviewer
# - Failed validators
```

### "Quota Exhausted"

```bash
# Check current quota
jq . tower/control/quota.json

# Options:
# 1. Wait for reset
# 2. Request increase
# 3. Pause non-critical work
```

### "Control Files Corrupted"

```bash
# 1. Find latest backup
ls -la tower/control/backups/

# 2. Restore from backup
bash tower/scripts/recover_control_state.sh --backup <backup_file>

# 3. Validate restored state
bash tower/scripts/validate_all.sh
```

## 6) Monitoring

### Health Checks

Run periodically (hourly or more):

```bash
bash tower/scripts/tower_watchdog.sh
```

### Drift Detection

Runs automatically. Check alerts:

```bash
cat tower/control/alerts/drift_alerts.json
```

### SLO Monitoring

```bash
python3 tower/addons/slo/compute_slo.py --write
cat tower/control/slo_status.json
```

## 7) Backup and Recovery

### Automated Backups

Backups are created automatically by various scripts. Check:

```bash
ls -la tower/control/backups/
```

### Manual Backup

```bash
cp tower/control/status.json "tower/control/backups/status_$(date +%Y%m%d%H%M%S).json"
```

### Recovery

```bash
# List available backups
ls -la tower/control/backups/

# Recover specific backup
bash tower/scripts/recover_control_state.sh --backup tower/control/backups/status_YYYYMMDD.json
```

## 8) Escalation

### When to Escalate

- Any S1 incident
- SLO breach lasting >24h
- Multiple failed merge attempts
- Control file corruption
- Unknown system behavior

### How to Escalate

1. Create incident in `tower/control/incidents/`
2. Tag card as ESCALATED
3. Notify team lead
4. Document in Kaizen proposal if systemic

## 9) Maintenance

### Weekly

- [ ] Review all ESCALATED cards
- [ ] Check SLO trends
- [ ] Review Kaizen proposals
- [ ] Clean up old artifacts (>30 days)

### Monthly

- [ ] Rotate old backups
- [ ] Review quota allocation
- [ ] Update documentation
- [ ] Run capacity analysis

### Quarterly

- [ ] Full system audit
- [ ] Review SLO thresholds
- [ ] Deprecation cleanup

## 10) Emergency Contacts

| Role | Responsibility |
|------|----------------|
| Ops Lead | Day-to-day operations |
| Tech Lead | Architecture decisions |
| On-Call | After-hours incidents |

## 11) Quick Reference Commands

```bash
# Validate everything
bash tower/scripts/validate_all.sh

# Check gates
bash tower/scripts/tower_gatecheck.sh

# Refresh dashboard
bash tower/scripts/tower_dashboard.sh

# Run watchdog
bash tower/scripts/tower_watchdog.sh

# Build proofpack
bash tower/scripts/tower_proofpack.sh --card CARD-XXX

# Merge to gold
bash tower/scripts/merge_gold.sh --card CARD-XXX --do-merge

# Check SLO
python3 tower/addons/slo/compute_slo.py --json

# Run evals
python3 tower/addons/evals/run_evals.py --all
```

---

*Tower Ops Runbook v1.5.5 | Last updated: 2026-01-17*
