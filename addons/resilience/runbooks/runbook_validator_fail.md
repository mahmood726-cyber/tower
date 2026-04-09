# Runbook: Validator Failure

## Trigger

- Validator reports FAIL status
- Card escalated due to validation
- Unexpected validation errors

## Severity

- **S3** for single card failure
- **S2** if affecting multiple cards
- **S1** if validator itself is broken

## Immediate Actions

1. **Check validator output**
   ```bash
   cat tower/artifacts/YYYY-MM-DD/<CARD>/run_*/validator_report.json
   ```

2. **Verify it's not a false positive**
   - Review the specific failures
   - Check if validator is up to date

3. **Hold card in current state**
   - Do not attempt to force through

## Investigation

1. **Understand the failure**
   - What specific check failed?
   - Is it a code issue or validator issue?
   - Any recent changes to validator?

2. **Check for patterns**
   - Other cards failing similarly?
   - Validator changed recently?

## Resolution

### Option A: Fix the card

If card genuinely has issues:
1. Return to ACTIVE state
2. Address the failures
3. Re-run validators

### Option B: Update validator

If validator is too strict or buggy:
1. Document the false positive
2. Update validator logic
3. Re-validate affected cards

### Option C: Manual override

If validator is wrong but can't be fixed immediately:
1. Document the exception
2. Create manual approval artifact
3. Proceed with human verification

## Post-Incident

1. **Track in metrics**
   - Record validator fail rate
   - Monitor for patterns

2. **Update validators**
   - Fix any identified issues
   - Improve error messages

## Escalation

Escalate to S2 if:
- Multiple cards blocked
- Validator appears broken
- Cannot determine if real failure
