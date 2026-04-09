# Tower Addons Architecture

**Version:** v1.5.7
**Last Updated:** 2026-01-18

## Overview

Tower addons extend the core Tower system without modifying its scripts. Each addon is self-contained with its own configuration, entry points, and outputs. Addons communicate through the shared control plane (`control/` directory).

## System Architecture

```
+------------------------------------------------------------------+
|                         Tower Core                                |
|  +------------------+  +------------------+  +------------------+ |
|  | tower_run.sh     |  | tower_validate   |  | tower_dashboard  | |
|  | tower_gatecheck  |  | tower_proofpack  |  | tower_backlog    | |
|  +--------+---------+  +--------+---------+  +--------+---------+ |
|           |                     |                     |           |
+-----------+---------------------+---------------------+-----------+
            |                     |                     |
            v                     v                     v
+------------------------------------------------------------------+
|                    Control Plane (control/)                       |
|  +-------------+  +-------------+  +-------------+  +-----------+ |
|  | status.json |  | backlog.md  |  | quota.json  |  | *.jsonl   | |
|  +-------------+  +-------------+  +-------------+  +-----------+ |
+------------------------------------------------------------------+
            ^                     ^                     ^
            |                     |                     |
+-----------+---------------------+---------------------+-----------+
|                         Addons Layer                              |
+------------------------------------------------------------------+
```

## Addon Categories

### Core Addons (enabled by default)
- **Ledger**: Hash-chained event logging
- **Evals**: Test runner with scoring
- **SLO**: Service level monitoring

### Tracing Addons
- **LangSmith**: LLM observability
- **MLflow**: Experiment tracking
- **Bridge**: Unified tracing wrapper

### Orchestration Addons
- **Prefect**: Workflow orchestration
- **Dagster**: Alternative orchestration

### Monitoring Addons
- **Resilience**: SPC, error budgets, dashboard overlay
- **GUI**: Local web interface

### Security Addons
- **Signing**: Cryptographic proofpack signing

### LLM Agent Addons
- **Autoclaude**: Production LLM agent patterns (14 modules)
  - Token/cost tracking, circuit breaker, retry policy
  - Prompt registry, human checkpoints, confidence scoring
  - Error taxonomy, fallback chains, rate limiting
  - Session management, output validation, state recovery
  - Guardrails (PII/injection), metrics export

## Addon Interaction Diagram

```
                              User/CI
                                 |
                                 v
                    +------------------------+
                    |       Tower GUI        |
                    |    (localhost:5000)    |
                    +------------------------+
                           |         |
              reads        |         |  triggers
          +----------------+         +------------------+
          v                                             v
+------------------+                        +------------------------+
|  Control Plane   |<-----------------------|    Tower Bridge        |
|                  |                        | (tower_run_with_addons)|
| - status.json    |         writes         +------------------------+
| - backlog.md     |<----------+                  |         |
| - quota.json     |           |           +------+         +------+
| - slo_status.json|           |           v                       v
| - event_ledger   |    +-------------+  +-------------+  +-------------+
|   .jsonl         |    | LangSmith   |  | MLflow      |  | Tower Core  |
+------------------+    | Adapter     |  | Wrapper     |  | tower_run.sh|
         ^              +-------------+  +-------------+  +-------------+
         |                    |                |                |
         |                    v                v                |
         |              +------------------------+              |
         |              |    Traces / Artifacts  |              |
         |              | - langsmith/traces/    |              |
         |              | - mlflow/mlruns/       |              |
         |              +------------------------+              |
         |                                                      |
         +------------------------------------------------------+
                                  |
                                  v
+------------------------------------------------------------------+
|                      Event Ledger                                 |
|  +------------------------------------------------------------+  |
|  | event_logger.py                                            |  |
|  |  - Hash-chained JSONL                                      |  |
|  |  - Cross-platform file locking                             |  |
|  |  - Tamper detection via prev_hash                          |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
                                  |
            +---------------------+----------------------+
            v                     v                      v
+------------------+   +------------------+   +------------------+
|   SLO Addon      |   | Resilience Addon |   |   Evals Addon    |
| - compute_slo.py |   | - tower_spc_     |   | - run_evals.py   |
| - slo_enforce.sh |   |   analyze.py     |   | - cases/*.json   |
+------------------+   | - tower_error_   |   +------------------+
         |             |   budget_update  |            |
         |             | - dashboard_plus |            |
         v             +------------------+            v
+------------------+            |            +------------------+
| slo_status.json  |            v            | evals_report.json|
+------------------+   +------------------+  | evals_score.csv  |
                       | dashboard_plus   |  +------------------+
                       |   .html          |
                       | dashboard_plus   |
                       |   _status.json   |
                       +------------------+
```

## Data Flow

### 1. Run Execution Flow

```
User Request
     |
     v
+--------------------+     +--------------------+
| tower_run_with_    | --> | tower_run.sh       |
| addons.py (Bridge) |     | (Core)             |
+--------------------+     +--------------------+
     |                              |
     | START event                  | creates
     v                              v
+--------------------+     +--------------------+
| Event Ledger       |     | artifacts/         |
| (event_logger.py)  |     | YYYY-MM-DD/card/   |
+--------------------+     | run_*/             |
     |                     +--------------------+
     | END event                    |
     v                              |
+--------------------+              |
| LangSmith/MLflow   |<-------------+
| (traces/artifacts) |   reads run_context.json
+--------------------+
```

### 2. Monitoring Flow

```
control/event_ledger.jsonl
          |
          +------------------+------------------+
          v                  v                  v
+------------------+  +------------------+  +------------------+
| compute_slo.py   |  | tower_spc_       |  | tower_error_     |
|                  |  | analyze.py       |  | budget_update.py |
+------------------+  +------------------+  +------------------+
          |                  |                  |
          v                  v                  v
+------------------+  +------------------+  +------------------+
| slo_status.json  |  | spc_alerts.json  |  | error_budget_    |
|                  |  |                  |  | status.json      |
+------------------+  +------------------+  +------------------+
          |                  |                  |
          +------------------+------------------+
                             |
                             v
                 +------------------------+
                 | tower_dashboard_plus.sh|
                 +------------------------+
                             |
                             v
                 +------------------------+
                 | dashboard_plus.html    |
                 | dashboard_plus_status  |
                 |   .json                |
                 +------------------------+
```

### 3. Validation Flow

```
+--------------------+
| User/CI triggers   |
| validation         |
+--------------------+
          |
          v
+--------------------+     +--------------------+
| run_evals.py       | --> | Execute test cases |
| --all              |     | from cases/*.json  |
+--------------------+     +--------------------+
          |                         |
          |                         v
          |                +--------------------+
          |                | tower_validate_all |
          |                | tower_gatecheck    |
          |                | etc.               |
          |                +--------------------+
          |                         |
          v                         v
+--------------------+     +--------------------+
| evals_report.json  |     | Pass/Fail results  |
| evals_score.csv    |     +--------------------+
+--------------------+
          |
          v
+--------------------+
| Event Ledger       |
| (EVAL_PASS/FAIL)   |
+--------------------+
```

## Security Boundaries

```
+------------------------------------------------------------------+
|                    TRUST BOUNDARY                                 |
|  +------------------------------------------------------------+  |
|  |                    User Input                               |  |
|  |  - card_id: validated ^[A-Za-z0-9_-]{1,50}$                |  |
|  |  - session: validated ^[A-Za-z0-9_.-]{1,100}$              |  |
|  |  - model:   validated ^[A-Za-z0-9_.:/-]{1,100}$            |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
          |
          v
+------------------------------------------------------------------+
|                    INPUT VALIDATION                               |
|  +------------------------------------------------------------+  |
|  | bridge/tower_run_with_addons.py:                           |  |
|  |   _validate_card_id(), _validate_session(), _validate_model|  |
|  |                                                             |  |
|  | gui/tower_gui.py:                                          |  |
|  |   _validate_card_id() before passing to scripts            |  |
|  |                                                             |  |
|  | evals/run_evals.py:                                        |  |
|  |   Path traversal protection: resolve().relative_to()       |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
          |
          v
+------------------------------------------------------------------+
|                    FILE OPERATIONS                                |
|  +------------------------------------------------------------+  |
|  | ledger/event_logger.py:                                    |  |
|  |   - 30s lock timeout (prevents deadlocks)                  |  |
|  |   - Atomic writes (temp + fsync + rename)                  |  |
|  |   - Cross-platform locking (msvcrt/fcntl)                  |  |
|  |                                                             |  |
|  | All addons:                                                 |  |
|  |   - Write only to designated output directories            |  |
|  |   - Never modify core Tower scripts                        |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
```

## File Structure

```
tower/
+-- addons/
|   +-- MANIFEST.json          # Addon registry and dependencies
|   +-- ARCHITECTURE.md        # This file
|   +-- README_ADDONS.md       # User documentation
|   |
|   +-- qa/
|   |   +-- schemas/           # JSON Schema definitions
|   |   |   +-- addon_event.schema.json
|   |   |   +-- bridge_run.schema.json
|   |   |   +-- eval_case.schema.json
|   |   |   +-- ledger_event.schema.json
|   |   |   +-- merge_freeze.schema.json
|   |   |   +-- slo_config.schema.json
|   |   |   +-- ...
|   |   +-- scripts/
|   |       +-- shellcheck_all.sh
|   |       +-- integration_test.py
|   |
|   +-- bridge/                # Unified tracing wrapper
|   +-- evals/                 # Test runner
|   +-- gui/                   # Web interface
|   +-- langsmith/             # LangSmith integration
|   +-- ledger/                # Event logging
|   +-- mlflow/                # MLflow integration
|   +-- prefect/               # Prefect orchestration
|   +-- resilience/            # Monitoring & dashboards
|   +-- signing/               # Cryptographic signing
|   +-- slo/                   # SLO monitoring
|   +-- dagster/               # Dagster orchestration
|   +-- autoclaude/            # Production LLM agent patterns
|       +-- __init__.py        # Package exports
|       +-- llm_tracker.py     # Token/cost tracking
|       +-- circuit_breaker.py # Loop prevention
|       +-- retry_policy.py    # Exponential backoff
|       +-- prompt_registry.py # Version-controlled prompts
|       +-- human_checkpoint.py# Human-in-the-loop gates
|       +-- confidence_scorer.py# Output confidence
|       +-- error_taxonomy.py  # Error classification
|       +-- fallback_chain.py  # Model degradation
|       +-- rate_limiter.py    # Token bucket limiting
|       +-- session_manager.py # Conversation context
|       +-- output_validator.py# JSON schema validation
|       +-- state_manager.py   # WAL crash recovery
|       +-- guardrails.py      # PII/injection safety
|       +-- metrics_exporter.py# Prometheus metrics
|
+-- control/                   # Shared control plane
|   +-- status.json
|   +-- backlog.md
|   +-- quota.json
|   +-- slo_status.json
|   +-- event_ledger.jsonl
|   +-- dashboard.html
|   +-- dashboard_plus.html
|   +-- ...
|
+-- scripts/                   # Core Tower scripts
|   +-- tower_run.sh
|   +-- tower_validate_all.sh
|   +-- tower_gatecheck.sh
|   +-- tower_dashboard.sh
|   +-- ...
|
+-- artifacts/                 # Run artifacts
    +-- YYYY-MM-DD/
        +-- CARD-XXX/
            +-- run_*/
```

## Addon Interface Contract

Each addon MUST:

1. **Not modify core scripts** - Addons wrap or extend, never patch
2. **Use control plane for state** - Read/write through `control/` directory
3. **Validate all inputs** - Use schemas from `qa/schemas/`
4. **Handle missing dependencies gracefully** - Print warning, continue
5. **Document entry points** - List in `MANIFEST.json`
6. **Provide README** - `README_<ADDON>.md` in addon directory

Each addon SHOULD:

1. **Emit events to ledger** - For audit trail
2. **Support dry-run mode** - For testing
3. **Use atomic file operations** - Prevent corruption
4. **Include test cases** - In `evals/cases/`

## Version Compatibility

| Addon Version | Tower Version | Notes |
|---------------|---------------|-------|
| 1.0.0         | v1.5.5+       | Initial release |

Addons follow semantic versioning. Breaking changes require major version bump.
