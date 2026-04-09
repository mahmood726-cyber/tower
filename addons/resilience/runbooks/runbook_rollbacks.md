# Runbook: Rollback Procedure

## Trigger

- Defect discovered in merged card
- Production issue traced to recent merge
- SLO breach requiring reversal

## Severity

- **S1** if causing active harm
- **S2** if degrading functionality
- **S3** if cosmetic or minor

## Immediate Actions

1. **Confirm the defect**
   - Verify the issue is real
   - Identify the problematic commit

2. **Stop further damage**
   ```bash
   echo '{"active": true, "reason": "Rollback in progress"}' > tower/control/merge_freeze.json
   ```

3. **Capture state before rollback**
   ```bash
   cp tower/control/status.json "tower/control/backups/status_$(date +%Y%m%d%H%M%S)_pre_rollback.json"
   ```

## Rollback Steps

1. **Identify the commit**
   ```bash
   git log --oneline gold -20
   ```

2. **Create revert commit**
   ```bash
   git checkout gold
   git revert <commit-sha>
   # Or for multiple commits:
   git revert <oldest-sha>..<newest-sha>
   ```

3. **Update card status**
   - Set affected card(s) to ROLLED_BACK
   - Update status.json

4. **Validate gold branch**
   ```bash
   bash tower/scripts/validate_all.sh
   bash tower/scripts/tower_gatecheck.sh
   ```

5. **Clear freeze when stable**
   ```bash
   rm tower/control/merge_freeze.json
   ```

## Post-Rollback

1. **Create incident report**
   - What was the defect?
   - How did it pass validation?
   - What is the fix plan?

2. **Update SLO tracking**
   - Rollback counts against SLO
   - May trigger error budget actions

3. **Create follow-up card**
   - Fix the underlying issue
   - Improve validation to catch it

## Root Cause Analysis

1. **Why did validation miss it?**
   - Coverage gap?
   - Edge case?
   - Validator bug?

2. **Process improvements**
   - Add test case
   - Update validator
   - Kaizen proposal if systemic

## Escalation

Escalate to S1 if:
- Rollback fails
- Gold branch corrupted
- Multiple related defects
