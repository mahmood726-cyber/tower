# Tower Resilience + Assurance Add-on

Comprehensive reliability engineering add-on for Tower. Provides STPA hazard analysis, assurance cases, SRE runbooks, SPC control charts, provenance tracking, and tamper-evident proofpacks.

## Overview

This add-on is purely additive - Tower core remains minimal. It provides:

- **STPA/Hazards**: Hazard register and unsafe control action analysis
- **Assurance Cases**: GSN-style structured arguments
- **SRE Runbooks**: Incident response procedures
- **SPC Charts**: Statistical process control for drift detection
- **Provenance**: Environment and dependency tracking
- **SLO/Error Budget**: Service level objective monitoring

## Quick Start

### Run SPC Analysis

```bash
python3 tower/addons/resilience/scripts/tower_spc_analyze.py
```

### Update Error Budget

```bash
python3 tower/addons/resilience/scripts/tower_error_budget_update.py
```

### Check Merge Gate (SLO-aware)

```bash
bash tower/addons/resilience/scripts/tower_merge_gate_slo.sh --card CARD-001
```

### Build Signed Proofpack

```bash
bash tower/addons/resilience/scripts/tower_proofpack_plus.sh --card CARD-001
```

### Capture Provenance

```bash
bash tower/addons/resilience/scripts/tower_capture_provenance.sh --out provenance.json
```

## Directory Structure

```
tower/addons/resilience/
  README_RESILIENCE.md        # This file
  schemas/                    # JSON schemas for resilience files
  scripts/                    # Runnable scripts
  hazards/                    # STPA hazard register
  assurance/                  # Assurance case templates
  runbooks/                   # SRE incident runbooks
  postmortems/               # Postmortem templates
  spc/                       # SPC analysis outputs
  provenance/                # Provenance capture
  templates/                 # Dashboard templates
```

## Control Files

These files may be created/updated by the add-on:

| File | Purpose |
|------|---------|
| `tower/control/slo_config.json` | SLO thresholds |
| `tower/control/error_budget_status.json` | Current error budget |
| `tower/control/merge_freeze.json` | Merge freeze status |
| `tower/control/alerts/spc_alerts.json` | SPC anomaly alerts |

## Scripts

### tower_spc_analyze.py

Performs statistical process control analysis on Tower metrics.

- Input: `tower/control/metrics.csv`
- Output: `tower/addons/resilience/spc/spc_report.md`, `tower/control/alerts/spc_alerts.json`

Uses individuals/moving range chart methodology with 3-sigma control limits.

### tower_error_budget_update.py

Updates error budget status based on SLO configuration.

- Input: `tower/control/slo_config.json`, `tower/control/metrics.csv`
- Output: `tower/control/error_budget_status.json`, `tower/control/merge_freeze.json`

Maintains rolling 30-day windows for SLO calculations.

### tower_merge_gate_slo.sh

Wrapper for merge_gold.sh that respects SLO-based freeze recommendations.

- If `merge_freeze.json` indicates freeze: blocks merge with reason
- Otherwise: delegates to `tower/scripts/merge_gold.sh`

### tower_proofpack_plus.sh

Builds a proofpack with provenance and hash manifest.

- Calls `tower/scripts/tower_proofpack.sh`
- Adds provenance capture
- Generates hash manifest

### tower_capture_provenance.sh

Captures environment provenance (no secrets).

Output includes:
- Git SHA and status
- Hostname, uname, Python version
- pip freeze (if venv exists)
- Timestamp

### tower_proofpack_hash.sh

Creates SHA256 manifest for proofpack files.

- Input: proofpack directory
- Output: `manifest_hashes.json`, optional GPG signature

### validate_resilience_files.py

Validates resilience control files against schemas.

- Uses jsonschema if available
- Exits non-zero on validation failure

## Hazard Analysis (STPA)

The hazard register at `hazards/HAZARD_REGISTER.json` documents:

- System-level hazards
- Unsafe control actions
- Causal scenarios
- Requirements/constraints

See `hazards/UNSAFE_CONTROL_ACTIONS.md` for detailed UCA analysis.

## Assurance Cases

Templates for GSN-style assurance arguments:

- `assurance/ASSURANCE_CASE_TEMPLATE.md`
- `assurance/assurance_case.example.json`

## Runbooks

Incident response procedures:

- `runbooks/runbook_drift.md` - Drift incident response
- `runbooks/runbook_quota.md` - Quota exhaustion
- `runbooks/runbook_validator_fail.md` - Validator failures
- `runbooks/runbook_rollbacks.md` - Rollback procedures
- `runbooks/runbook_control_corruption.md` - Control file recovery

## Postmortems

Template at `postmortems/POSTMORTEM_TEMPLATE.md` for incident documentation.

## SLO Defaults

| Metric | Target | Breach |
|--------|--------|--------|
| Rollback rate (monthly) | < 3% | >= 5% |
| Validator fail rate | < 15% | >= 25% |
| Reviewer disagreement | < 10% | >= 15% |
| Drift incidents/100h | < 2 | >= 4 |

## Safety Notes

- **No secrets**: Provenance capture excludes sensitive data
- **Signing optional**: Hash manifest created even without GPG
- **Read-only by default**: Scripts don't modify Tower core
- **Atomic writes**: All JSON updates use temp+fsync+rename

## Next Actions

1. Run validation:
   ```bash
   python3 tower/addons/resilience/scripts/validate_resilience_files.py
   ```

2. Set up SPC baseline:
   ```bash
   python3 tower/addons/resilience/scripts/tower_spc_analyze.py
   ```

3. Review hazard register:
   ```bash
   cat tower/addons/resilience/hazards/HAZARD_REGISTER.json | python3 -m json.tool
   ```

---

*Tower Resilience Add-on v1.5.5*
