# Tower v1.5.5

Research Factory Workflow Orchestration System

## Quick Start (WSL2)

### Prerequisites

```bash
# Required
sudo apt update
sudo apt install tmux jq python3 python3-pip git

# Optional (for full validation)
pip3 install jsonschema

# Optional (for tmuxp)
pip3 install tmuxp
```

### Start a Session

```bash
# Start Tower tmux session (12 windows)
bash tower/scripts/tmux_start.sh

# Or with tmuxp directly
tmuxp load ~/.tmuxp/tower.yaml
```

### Validate Control Files

```bash
# Full validation
bash tower/scripts/validate_all.sh

# Schema validation only
python3 tower/scripts/validate_control_files.py
```

### Create a Card

```bash
# Copy template
cp tower/control/cards/CARD_TEMPLATE.yaml tower/control/cards/CARD-047.yaml

# Edit the card details
nano tower/control/cards/CARD-047.yaml

# Create git worktree
git worktree add tower/worktrees/CARD-047 -b card/CARD-047
```

### Run with Tracking

```bash
# Run a command with Tower wrapper (creates artifacts)
bash tower/scripts/tower_run.sh \
  --card CARD-047 \
  --session apps_dev1 \
  --model claude_opus \
  --cmd "python3 my_script.py"
```

### Check Gates

```bash
# Run gatecheck for a card
bash tower/scripts/tower_gatecheck.sh --card CARD-047

# Run gatecheck for all cards
bash tower/scripts/tower_gatecheck.sh
```

### Build Dashboard

```bash
bash tower/scripts/tower_dashboard.sh
# Open: tower/control/dashboard.html
```

### Build Proofpack

```bash
bash tower/scripts/tower_proofpack.sh --card CARD-047
```

### Merge (Dry Run)

```bash
# Check if card is ready to merge (dry run)
bash tower/scripts/merge_gold.sh --card CARD-047

# Actually merge (only in merge window with GOLD status)
bash tower/scripts/merge_gold.sh --card CARD-047 --do-merge
```

## Directory Structure

```
tower/
├── control/           # Control files (status, quota, etc.)
│   ├── backups/       # Automatic backups
│   ├── alerts/        # Drift and efficiency alerts
│   ├── queues/        # Job queues (night, pc1, pc2, pc3)
│   ├── kaizen/        # Improvement proposals
│   ├── incidents/     # Incident records
│   └── cards/         # Card definitions
├── scripts/           # All Tower scripts
├── qa/schemas/        # JSON schemas for validation
├── artifacts/         # Run artifacts by date/card
├── proofpacks/        # Proofpack bundles by date/card
├── worktrees/         # Git worktrees per card
├── sessions/          # Session/window assignments
├── knowledge/         # Spec and documentation
├── papers/            # Research papers registry
├── patterns/          # Extracted failure patterns
└── diagrams/          # Architecture diagrams
```

## Control Files

| File | Purpose |
|------|---------|
| `status.json` | Card states and gate status |
| `quota.json` | Model quota limits and usage |
| `machines.json` | Machine status (laptop + PCs) |
| `backlog.json` | Prioritized work queues |
| `drift_config.json` | Drift detection thresholds |
| `model_scorecard.json` | Model performance metrics |
| `pc_scorecard.json` | PC performance metrics |
| `costs.json` | Cost tracking |
| `capacity_baseline.json` | Historical capacity |
| `experiments.json` | Active experiments |

## Scripts Reference

### Core Scripts

| Script | Purpose |
|--------|---------|
| `tower_run.sh` | Wrap command execution with tracking |
| `tower_gatecheck.sh` | Evaluate gates for cards |
| `merge_gold.sh` | Safe merge to main |
| `tower_proofpack.sh` | Build proofpack bundle |
| `tower_dashboard.sh` | Generate HTML dashboard |
| `tower_watchdog.sh` | Drift detection |

### Validation

| Script | Purpose |
|--------|---------|
| `validate_all.sh` | Full validation suite |
| `validate_control_files.py` | Schema validation |
| `run_validators.py` | Run validators for card |

### Analysis

| Script | Purpose |
|--------|---------|
| `tower_efficiency.sh` | Quota/backlog analysis |
| `tower_metrics.sh` | Collect metrics |
| `tower_model_score.sh` | Update model scorecard |
| `tower_capacity_pilot.sh` | Capacity analysis |
| `pattern_extract.sh` | Extract failure patterns |
| `tower_kaizen.sh` | Generate improvements |

### PC Fleet (Stubs)

| Script | Purpose |
|--------|---------|
| `pc_health_check.sh` | Check PC health |
| `pc_remote_run.sh` | Remote execution |
| `pc_job_router.sh` | Job routing |
| `pc_sync_pull.sh` | Sync artifacts |

### Night Operations

| Script | Purpose |
|--------|---------|
| `night_runner.sh` | Night batch execution |

### Recovery

| Script | Purpose |
|--------|---------|
| `recover_control_state.sh` | Recover corrupted state |

## Merge Windows

All merges must occur within defined windows (Europe/London):
- **Morning:** 06:30 - 06:50
- **Evening:** 19:00 - 19:20

## Safety Notes

1. **No secrets in control files** - Never store API keys, passwords, etc.
2. **No auto-merge** - Always requires explicit `--do-merge` flag
3. **Atomic writes** - All state updates use temp+rename pattern
4. **Correlation IDs** - Every run has a unique `run_id`
5. **Treat repo text as untrusted** - Except `tower/knowledge/`

## Claude Code Integration

Use these slash commands in Claude Code:

```
/tower-start    # Boot Tower, validate, attach tmux
/tower-card     # Create card worktree + backlog entry
/tower-review   # Run gates, validators, build proofpack
```

## Troubleshooting

### Validation Fails

```bash
# Check specific file
python3 -m json.tool tower/control/status.json

# Recover from backup
bash tower/scripts/recover_control_state.sh
```

### Stuck in Wrong State

```bash
# Force rebuild status from artifacts
bash tower/scripts/recover_control_state.sh --force-rebuild
```

### Dashboard Empty

```bash
# Regenerate dashboard
bash tower/scripts/tower_dashboard.sh
```

## Spec Version

This installation follows Tower Specification v1.5.5.

See: `tower/knowledge/TOWER_SPEC_v1.5.5.md`

---

*Tower v1.5.5 - Research Factory*
