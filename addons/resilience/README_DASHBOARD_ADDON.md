# Dashboard Plus Add-on

Overlays Tower's existing dashboard with a Resilience & Assurance status panel.

## Overview

Dashboard Plus adds a visual status badge to Tower's dashboard without modifying any existing Tower scripts. It:

1. Reads Tower control files to assess system health
2. Computes an overall status (GREEN/YELLOW/RED/FREEZE/UNKNOWN)
3. Injects a styled panel after the `<body>` tag
4. Outputs to `tower/control/dashboard_plus.html`

## Quick Start

```bash
# Generate dashboard with resilience panel
bash tower/addons/resilience/scripts/tower_dashboard_plus.sh

# Skip base dashboard regeneration (faster)
bash tower/addons/resilience/scripts/tower_dashboard_plus.sh --no-regenerate

# View result
open tower/control/dashboard_plus.html
```

## Status Priority

Status is computed with the following priority (highest wins):

| Priority | Status | Condition |
|----------|--------|-----------|
| 1 | **FREEZE** | `merge_freeze.json` exists and `active == true` |
| 2 | **RED** | Error budget < 0% OR SLO breached |
| 3 | **YELLOW** | SPC alerts > 0 OR drift alerts > 0 |
| 4 | **GREEN** | All checks pass, `status.json` exists |
| 5 | **UNKNOWN** | Insufficient data to determine status |

## Control Files Read

| File | Purpose |
|------|---------|
| `merge_freeze.json` | Merge freeze status |
| `error_budget_status.json` | Error budget remaining |
| `slo_status.json` | SLO compliance |
| `spc_alerts.json` | Statistical process control alerts |
| `drift_alerts.json` | State drift alerts |
| `status.json` | Card status for active count |

## Output Files

| File | Description |
|------|-------------|
| `dashboard_plus.html` | Enhanced dashboard with resilience panel |
| `dashboard_plus_status.json` | Machine-readable status summary |

## Panel Appearance

The panel displays:

- **Status Badge**: Color-coded status indicator (GREEN/YELLOW/RED/FREEZE/UNKNOWN)
- **Error Budget**: Remaining budget percentage
- **SLO Status**: Current SLO compliance
- **Active Cards**: Number of cards in ACTIVE state
- **Alert Tags**: Quick indicators for freeze, SPC, drift, and budget issues
- **Timestamp**: Last update time

### Status Colors

| Status | Background | Border |
|--------|------------|--------|
| GREEN | Light green gradient | #28a745 |
| YELLOW | Light amber gradient | #ffc107 |
| RED | Light red gradient | #dc3545 |
| FREEZE | Light blue gradient | #004085 (pulsing) |
| UNKNOWN | Light gray gradient | #6c757d |

## Integration

### With Night Runner

Add to `tower_night_runner.sh`:

```bash
# Generate dashboard plus after main dashboard
bash tower/addons/resilience/scripts/tower_dashboard_plus.sh --no-regenerate
```

### With Cron

```cron
# Regenerate dashboard plus every 15 minutes
*/15 * * * * cd /path/to/project && bash tower/addons/resilience/scripts/tower_dashboard_plus.sh --no-regenerate
```

### As Post-Merge Hook

```bash
# In post-merge hook
bash tower/addons/resilience/scripts/tower_dashboard_plus.sh
```

## Customization

### Template

Edit `tower/addons/resilience/templates/resilience_panel_template.html` to customize:

- Panel styling (CSS)
- Metrics displayed
- Alert tag appearance

### Placeholders

Available placeholders in the template:

| Placeholder | Description |
|-------------|-------------|
| `{{STATUS}}` | Status text (GREEN, YELLOW, etc.) |
| `{{STATUS_LOWER}}` | Lowercase status for CSS classes |
| `{{ERROR_BUDGET_REMAINING}}` | Remaining budget with % |
| `{{SLO_STATUS}}` | SLO status text |
| `{{ACTIVE_CARDS}}` | Count of active cards |
| `{{ALERT_TAGS}}` | HTML for alert indicator tags |
| `{{TIMESTAMP}}` | ISO timestamp |

## Example Status JSON

```json
{
  "generated_at": "2025-01-17T10:30:00Z",
  "status": "GREEN",
  "is_frozen": false,
  "freeze_reason": "",
  "error_budget_remaining": "75.5%",
  "error_budget_depleted": false,
  "slo_status": "MET",
  "slo_breached": false,
  "spc_alert_count": 0,
  "drift_alert_count": 0,
  "active_cards": 3,
  "output_file": "/path/to/tower/control/dashboard_plus.html"
}
```

## Non-Invasive Design

This add-on is designed to be completely non-invasive:

- **Does NOT modify** existing Tower scripts
- **Does NOT alter** the base `dashboard.html`
- **Creates separate** output files (`dashboard_plus.html`, `dashboard_plus_status.json`)
- **Fails gracefully** if control files are missing
- **Can be removed** without affecting Tower functionality

## Troubleshooting

### Panel Not Appearing

1. Check that base dashboard exists: `ls tower/control/dashboard.html`
2. Verify template exists: `ls tower/addons/resilience/templates/`
3. Check script output for errors

### Incorrect Status

1. Review control files manually with `jq`
2. Check `dashboard_plus_status.json` for computed values
3. Verify JSON syntax in control files

### Styling Issues

1. Check for CSS conflicts with base dashboard
2. Review browser console for errors
3. Test with a minimal HTML file
