# Runbook: Quota Exhaustion

## Trigger

- Quota check fails
- Token budget exceeded alert
- Model unavailable due to limits

## Severity

- **S2** if blocking critical path
- **S3** if workaround available

## Immediate Actions

1. **Check current quota**
   ```bash
   cat tower/control/quota.json
   ```

2. **Identify consumption**
   ```bash
   # Check recent runs
   cat tower/control/metrics.csv | tail -20

   # Check which cards are consuming
   bash tower/scripts/tower_efficiency.sh
   ```

3. **Pause non-critical work**
   - Prioritize cards closest to completion
   - Defer exploratory work

## Investigation

1. **Usage analysis**
   - Which model is exhausted?
   - Which cards consumed the most?
   - Any anomalous consumption?

2. **Budget review**
   - Was quota appropriately sized?
   - Unexpected demand?

## Resolution

### Option A: Wait for reset

If reset is imminent:
- Document in backlog
- Resume after reset

### Option B: Reallocate

If other models have capacity:
- Update card configurations
- Use alternative models

### Option C: Request increase

If justified:
- Document usage and need
- Request quota increase
- Create Kaizen proposal for better forecasting

## Post-Incident

1. **Update forecasts**
   - Revise quota estimates

2. **Review efficiency**
   ```bash
   bash tower/scripts/tower_efficiency.sh
   ```

3. **Consider Kaizen**
   - If pattern repeats, propose improvements

## Prevention

- Monitor quota weekly
- Set alerts at 80% consumption
- Track tokens per GREEN card
