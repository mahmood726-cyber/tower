# Tower SLO + Error Budget Addon

Service Level Objectives (SLO) monitoring and error budget automation for Tower.

## Overview

This addon provides:
- **SLO computation**: Calculate SLO status from Tower metrics
- **Dashboard fragments**: Generate HTML snippets for SLO status
- **Error budget enforcement**: Recommend merge freezes when SLOs are breached

## Installation

No additional dependencies. Uses Python 3 standard library.

## Configuration

Edit `tower/addons/slo/slo_config.json` to customize thresholds:

```json
{
  "timezone": "Europe/London",
  "windows_days": [7, 30],
  "thresholds": {
    "rollback_rate_monthly_pct": {"target": 3, "breach": 5},
    "validator_fail_rate_pct": {"target": 15, "breach": 25},
    "glm_pass_audit_disagreement_pct": {"target": 10, "breach": 15},
    "drift_incidents_per_100_active_hours": {"target": 2, "breach": 4}
  }
}
```

## Usage

### Compute SLO Status

```bash
python3 tower/addons/slo/compute_slo.py --write
```

This reads:
- `tower/control/metrics.csv` (if present)
- `tower/control/status.json` (if present)
- `tower/control/alerts/drift_alerts.json` (if present)

And writes:
- `tower/control/slo_status.json`
- `tower/control/alerts/slo_breaches.json` (if breaches exist)
- `tower/addons/slo/artifacts/YYYY-MM-DD/slo_report_<run_id>.md`

### Render Dashboard Fragment

```bash
python3 tower/addons/slo/render_slo_fragment.py
```

Generates an HTML fragment at:
- `tower/addons/slo/artifacts/YYYY-MM-DD/slo_fragment_<run_id>.html`

### Enforce SLO (Freeze Recommendation)

```bash
bash tower/addons/slo/slo_enforce.sh
```

If SLOs are breached, writes:
- `tower/control/alerts/error_budget_actions.json`

## SLO Metrics

| Metric | Target | Breach | Description |
|--------|--------|--------|-------------|
| `rollback_rate_monthly_pct` | < 3% | >= 5% | Monthly rollback rate |
| `validator_fail_rate_pct` | < 15% | >= 25% | Validator failure rate |
| `glm_pass_audit_disagreement_pct` | < 10% | >= 15% | GLM pass/audit disagreement |
| `drift_incidents_per_100_active_hours` | < 2 | >= 4 | Drift incidents per 100 active hours |

## Output Files

### tower/control/slo_status.json

```json
{
  "spec_version": "v1.5.5",
  "last_updated": "2026-01-17T10:30:00Z",
  "overall_status": "OK",
  "metrics": {
    "rollback_rate_monthly_pct": {
      "value": 1.5,
      "target": 3,
      "breach": 5,
      "status": "OK"
    }
  },
  "window_days": 30,
  "notes": []
}
```

### tower/control/alerts/error_budget_actions.json

When SLOs are breached:

```json
{
  "spec_version": "v1.5.5",
  "created_at": "2026-01-17T10:30:00Z",
  "active": true,
  "reason": "SLO breach: rollback_rate_monthly_pct exceeded",
  "recommended_actions": [
    "Freeze merges for 24h (recommendation only)",
    "Increase PASS audit sampling",
    "Run nightly evals",
    "Open Kaizen proposal"
  ]
}
```

## Integration with merge_gold.sh

The SLO enforce script writes recommendations only. To integrate with merge workflow:

1. Use `tower/addons/slo/slo_guard.sh` as a wrapper:
   ```bash
   bash tower/addons/slo/slo_guard.sh --card CARD-001
   ```

2. Or check `slo_freeze_recommendation.json` manually before merging.

## Troubleshooting

**"No data available"**: SLOs show UNKNOWN when metrics files are missing.

**"Breach detected but no freeze"**: Freeze is a recommendation, not enforced automatically.

**"stale data"**: Re-run `compute_slo.py` to refresh status.
