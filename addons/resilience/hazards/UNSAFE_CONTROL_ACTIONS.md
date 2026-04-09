# Tower Unsafe Control Actions (UCA) Analysis

## Overview

This document analyzes unsafe control actions for Tower v1.5.5 using STPA methodology.

## Control Actions

### CA-1: Merge Card to Gold

| Type | Context | UCA | Hazard | Constraint |
|------|---------|-----|--------|------------|
| Not Provided | Card passes all gates | Merge not executed | H-002 | System must merge when gates pass |
| Provided | Card has not passed gates | Merge executed anyway | H-002 | System must not merge without PASS |
| Too Early | Card recently changed | Merge before re-validation | H-002 | Validation required after changes |
| Too Late | SLO breach active | Merge during freeze | H-007 | Respect error budget freeze |

### CA-2: Validate Control Files

| Type | Context | UCA | Hazard | Constraint |
|------|---------|-----|--------|------------|
| Not Provided | Files modified | Skip validation | H-001 | Validate after every modification |
| Provided | Invalid files | Validation passes | H-001 | Validation must catch all errors |
| Too Late | After operations | Validate after the fact | H-001 | Validate before operations |

### CA-3: Run Drift Detection

| Type | Context | UCA | Hazard | Constraint |
|------|---------|-----|--------|------------|
| Not Provided | System running | Watchdog disabled | H-004 | Watchdog must run continuously |
| Too Late | Drift already caused damage | Detection after cascade | H-004 | Detect before impact |
| Stopped Too Soon | During investigation | Watchdog stopped | H-004 | Maintain monitoring during incidents |

### CA-4: Execute Rollback

| Type | Context | UCA | Hazard | Constraint |
|------|---------|-----|--------|------------|
| Not Provided | Defect detected | Rollback not executed | H-007 | Rollback when defect confirmed |
| Provided | No defect | Unnecessary rollback | - | Only rollback confirmed defects |
| Too Late | Cascade in progress | Slow rollback | H-007 | Rollback within SLO window |

## Causal Scenarios

### S-001: Merge Without Gates

**Scenario**: Developer uses --force flag to bypass gate checks.

**Causal Factors**:
- Gate check takes too long
- Pressure to ship
- Misunderstanding of risks

**Controls**:
- Audit log of --force usage
- Require justification
- Alert on --force

### S-002: Validation Bypass

**Scenario**: Script modified but validation not run.

**Causal Factors**:
- Manual editing
- Forgot to validate
- Script error suppressed

**Controls**:
- Pre-commit hooks
- Watchdog monitoring
- Mandatory validation in workflow

### S-003: Drift Accumulation

**Scenario**: Small drifts accumulate unnoticed.

**Causal Factors**:
- Watchdog threshold too high
- Alert fatigue
- Drift in non-critical fields

**Controls**:
- SPC-based anomaly detection
- Trend monitoring
- Regular reconciliation

## Safety Requirements

| ID | Requirement | Derived From |
|----|-------------|--------------|
| SR-001 | Merge requires PASS status | UCA-002 |
| SR-002 | Validation runs before operations | UCA-003 |
| SR-003 | Watchdog runs continuously | UCA-004 |
| SR-004 | SLO freeze blocks merges | H-007 |
| SR-005 | Proofpacks have hash manifest | H-006 |
| SR-006 | Backups created before changes | H-001 |

---

*STPA Analysis for Tower v1.5.5*
