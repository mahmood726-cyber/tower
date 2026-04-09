# Tower v1.5.7 Architecture

## Overview

Tower is a modular addon system for LLM-powered workflow automation with built-in observability, self-correction, and compliance features.

## System Diagram

```
                                    +------------------+
                                    |   Tower Core     |
                                    |   (tower_run.sh) |
                                    +--------+---------+
                                             |
              +------------------------------+------------------------------+
              |                              |                              |
     +--------v--------+            +--------v--------+            +--------v--------+
     |     Bridge      |            |     Ledger      |            |   Resilience    |
     | (Unified Tracer)|            | (Event Logger)  |            |  (SPC + SLO)    |
     +--------+--------+            +--------+--------+            +--------+--------+
              |                              |                              |
     +--------+--------+                     |                     +--------+--------+
     |                 |                     |                     |                 |
+----v----+      +-----v-----+         +-----v-----+         +-----v-----+     +-----v-----+
|LangSmith|      |  MLflow   |         |  control/ |         |    SLO    |     |  Signing  |
| Tracing |      | Tracking  |         |ledger.jsonl         | Monitoring|     | Proofpack |
+---------+      +-----------+         +-----------+         +-----------+     +-----------+
```

## Addon Architecture

### Core Addons (Always Available)
```
+-------------------+     +-------------------+     +-------------------+
|      Ledger       |---->|       SLO         |---->|    Resilience     |
| Hash-chained logs |     | Service Levels    |     | SPC + Error Budget|
+-------------------+     +-------------------+     +-------------------+
        |                         |                         |
        v                         v                         v
 event_ledger.jsonl        slo_status.json         dashboard_plus.html
```

### Tracing Addons (Optional)
```
+-------------------+     +-------------------+
|    LangSmith      |     |      MLflow       |
|  LLM Observability|     | Experiment Track  |
+-------------------+     +-------------------+
        \                       /
         \                     /
          v                   v
      +-------------------+
      |      Bridge       |
      | Unified Wrapper   |
      +-------------------+
```

### Orchestration Addons (Optional)
```
+-------------------+     +-------------------+
|     Prefect       |     |     Dagster       |
| Workflow Orchestr |     | Data Orchestrator |
+-------------------+     +-------------------+
```

### GUI Addon (Optional)
```
+-------------------+
|    Tower GUI      |
| Flask Web UI      |
| - Dashboard View  |
| - Kanban Board    |
| - Metrics Panel   |
| - Event Browser   |
| - Self-Correct    |
| - Validator       |
+-------------------+
        |
        v
 http://localhost:5000
```

### Autoclaude Addon (Production LLM Patterns)
```
+---------------------+     +---------------------+     +---------------------+
|    LLM Tracker      |     |  Circuit Breaker    |     |   Retry Policy      |
| - Token counting    |     | - Failure threshold |     | - Exponential back  |
| - Cost tracking     |     | - Auto-recovery     |     | - Jitter support    |
| - Budget enforce    |     | - Escalation        |     | - Async support     |
+---------------------+     +---------------------+     +---------------------+
          |                           |                           |
          +---------------------------+---------------------------+
                                      |
                                      v
+---------------------+     +---------------------+     +---------------------+
|  Prompt Registry    |     | Human Checkpoint    |     | Confidence Scorer   |
| - Version control   |     | - Risk-based gates  |     | - Multi-heuristic   |
| - Hash-based IDs    |     | - Approval workflow |     | - Threshold routing |
| - A/B testing       |     | - Timeout handling  |     | - Calibration       |
+---------------------+     +---------------------+     +---------------------+
          |                           |                           |
          +---------------------------+---------------------------+
                                      |
                                      v
+---------------------+     +---------------------+     +---------------------+
|  Error Taxonomy     |     |  Fallback Chain     |     |   Rate Limiter      |
| - Pattern matching  |     | - Model degradation |     | - Token bucket      |
| - Severity levels   |     | - Quality fallback  |     | - Per-scope limits  |
| - Auto-fix hints    |     | - Cost optimization |     | - Async support     |
+---------------------+     +---------------------+     +---------------------+
```

## Dependency Graph

```
resilience ──────┬──> slo ──────> ledger
                 │
                 └──> ledger

bridge ──────────┬──> langsmith
                 │
                 └──> mlflow

autoclaude ──────────> ledger
```

## Data Flow

### 1. Event Logging Flow
```
User Action ──> tower_run.sh ──> log_event.sh ──> event_logger.py
                                                         |
                                                         v
                                              event_ledger.jsonl
                                              (hash-chained JSONL)
```

### 2. SLO Computation Flow
```
event_ledger.jsonl ──> compute_slo.py ──> slo_status.json
        |                    |                   |
        v                    v                   v
 Historical Data      Threshold Check     Alert Generation
        |                    |                   |
        +--------------------+-------------------+
                             |
                             v
                    slo_breaches.json (if breach)
```

### 3. Self-Correcting Workflow
```
+----------+     +----------+     +----------+     +----------+
| VALIDATE |────>| ANALYZE  |────>| CORRECT  |────>|  VERIFY  |
|          |     |          |     |          |     |          |
| Run tests|     | Find root|     | Apply    |     | Re-run   |
| & checks |     | cause    |     | fixes    |     | tests    |
+----+-----+     +----------+     +----------+     +-----+----+
     |                                                   |
     |  FAIL                                      PASS   |
     +---------------------------------------------------+
                             |
                             v
                        GREEN STATE
```

## Control Plane

All shared state lives in `tower/control/`:

```
control/
├── status.json           # Current system state
├── event_ledger.jsonl    # Append-only event log
├── slo_status.json       # SLO metrics and status
├── dashboard_plus.html   # Generated dashboard
├── alerts/
│   ├── slo_breaches.json # SLO breach alerts
│   ├── drift_alerts.json # Drift detection alerts
│   └── spc_alerts.json   # SPC control alerts
└── backups/
    └── event_ledger_*.jsonl  # Rotated logs
```

## File Structure

```
tower/
├── addons/
│   ├── MANIFEST.json          # Addon registry & dependencies
│   ├── bridge/                # Unified tracing wrapper
│   │   └── tower_run_with_addons.py
│   ├── dagster/               # Dagster orchestration
│   │   └── definitions.py
│   ├── evals/                 # Evaluation framework
│   │   ├── run_evals.py
│   │   └── artifacts/
│   ├── gui/                   # Web interface
│   │   ├── tower_gui.py
│   │   ├── tower_dashboard.html
│   │   ├── tower_dashboard.css
│   │   └── tower_dashboard.js
│   ├── langsmith/             # LangSmith tracing
│   │   ├── langsmith_adapter.py
│   │   └── trace_local.py
│   ├── ledger/                # Event logging
│   │   ├── event_logger.py
│   │   └── log_event.sh
│   ├── mlflow/                # MLflow tracking
│   │   └── mlflow_run_wrapper.py
│   ├── prefect/               # Prefect orchestration
│   │   ├── prefect_flows.py
│   │   └── flows/
│   ├── qa/                    # Quality assurance
│   │   ├── schemas/           # JSON Schemas
│   │   └── scripts/           # Test scripts
│   ├── resilience/            # SPC & monitoring
│   │   └── scripts/
│   ├── signing/               # Cryptographic signing
│   │   └── proofpack_*.sh
│   ├── slo/                   # SLO monitoring
│   │   ├── compute_slo.py
│   │   └── slo_config.json
│   └── autoclaude/            # Production LLM patterns
│       ├── __init__.py
│       ├── llm_tracker.py     # Token/cost tracking
│       ├── circuit_breaker.py # Runaway loop prevention
│       ├── retry_policy.py    # Exponential backoff
│       ├── prompt_registry.py # Prompt versioning
│       ├── human_checkpoint.py # Human-in-the-loop
│       ├── confidence_scorer.py # Output confidence
│       ├── error_taxonomy.py  # Error classification
│       ├── fallback_chain.py  # Model degradation
│       └── rate_limiter.py    # Token bucket limiting
├── control/                   # Shared state
├── scripts/                   # Core scripts
│   └── tower_run.sh
└── ARCHITECTURE.md            # This file
```

## JSON Schema Validation

All inputs are validated against JSON Schema (Draft 2020-12):

| Schema | Purpose |
|--------|---------|
| `ledger_event.schema.json` | Event logging validation |
| `slo_config.schema.json` | SLO configuration |
| `bridge_run.schema.json` | Bridge wrapper inputs |
| `gui_status.schema.json` | GUI state model |
| `eval_case.schema.json` | Evaluation test cases |
| `merge_freeze.schema.json` | Merge gate configuration |
| `dashboard_plus_status.schema.json` | Dashboard data model |
| `orchestrator_run.schema.json` | Orchestration inputs |
| `addon_event.schema.json` | Generic addon events |

## Security Model

### Input Validation
- All inputs validated via JSON Schema
- Path traversal protection in file operations
- Command injection prevention via allowlists

### Hash Chain Integrity
- Each event includes SHA-256 hash
- Hash chain links to previous event
- Tamper detection via chain verification

### Cross-Platform Locking
- Windows: `msvcrt.locking()`
- Unix: `fcntl.flock()`
- Timeout-based acquisition (30s default)
- No race conditions in lock release

## Configuration

### Environment Variables
| Variable | Addon | Purpose |
|----------|-------|---------|
| `LANGSMITH_API_KEY` | langsmith | API authentication |
| `MLFLOW_TRACKING_URI` | mlflow | Tracking server URL |
| `TOWER_BRIDGE_LANGSMITH_ENABLE` | bridge | Enable LangSmith |
| `TOWER_BRIDGE_MLFLOW_ENABLE` | bridge | Enable MLflow |
| `TOWER_GUI_PORT` | gui | Server port (default: 5000) |
| `TOWER_GUI_HOST` | gui | Server host (default: 127.0.0.1) |
| `TOWER_GUI_READONLY` | gui | Read-only mode |
| `TOWER_SIGNING_KEY` | signing | Proofpack signing key |

### Addon Groups
| Group | Addons | Default |
|-------|--------|---------|
| Core | ledger, evals, slo | Enabled |
| Tracing | langsmith, mlflow, bridge | Disabled |
| Orchestration | prefect, dagster | Disabled |
| Monitoring | resilience, gui | Mixed |
| Security | signing | Disabled |
| Autoclaude | autoclaude | Enabled |

## Testing

### Integration Tests
```bash
python tower/addons/qa/scripts/integration_test.py
```

Tests include:
- Schema validation (9 schemas)
- Manifest integrity
- Event ledger operations
- Bridge input validation
- GUI module imports
- Evals path traversal protection
- SLO configuration
- Cross-addon workflows
- E2E self-correcting workflow
- Historical SLO computation

### Current Test Count
- 30 integration tests
- 100% pass rate target

## Version History

| Version | Changes |
|---------|---------|
| v1.5.7 | Added error taxonomy, fallback chain, rate limiter to autoclaude |
| v1.5.6 | Added autoclaude addon (LLM tracker, circuit breaker, retry, prompts, checkpoints, confidence) |
| v1.5.5 | Added GUI addon, E2E tests, historical SLO |
| v1.5.4 | Added resilience addon, SPC monitoring |
| v1.5.3 | Added signing addon, proofpack |
| v1.5.2 | Added prefect/dagster orchestration |
| v1.5.1 | Added bridge unified wrapper |
| v1.5.0 | Initial addon architecture |

---

*Generated for Tower v1.5.7*
