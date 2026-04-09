# Tower Bridge Addon

Optional wrapper that adds tracing + experiment logging to Tower runs. Tower core stays minimal.

## Purpose

The bridge wraps `tower/scripts/tower_run.sh` and emits:
- **LangSmith traces** (always local, optionally remote)
- **MLflow logging** (if installed and configured)

This is purely additive - Tower runs normally without it.

## Usage

```bash
python3 tower/addons/bridge/tower_run_with_addons.py \
  --card CARD-001 \
  --session apps_dev1 \
  --model claude_opus \
  --cmd "bash tower/scripts/tower_dashboard.sh"
```

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--card` | Card ID | Yes |
| `--session` | Session name | Yes |
| `--model` | Model name | Yes |
| `--cmd` | Command to execute | Yes |
| `--tags` | Comma-separated tags | No |
| `--note` | Optional note | No |
| `--dry-run` | Print what would happen, don't run | No |

## Configuration

Copy and edit the env file:

```bash
cp tower/addons/bridge/bridge.env.example tower/addons/bridge/.env
source tower/addons/bridge/.env
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TOWER_BRIDGE_LANGSMITH_ENABLE` | Enable LangSmith tracing | `1` |
| `TOWER_BRIDGE_MLFLOW_ENABLE` | Enable MLflow logging | `1` |
| `MLFLOW_TRACKING_URI` | MLflow tracking store | `file:./tower/addons/mlflow/mlruns` |
| `MLFLOW_EXPERIMENT_NAME` | MLflow experiment | `tower` |
| `LANGSMITH_PROJECT` | LangSmith project | `tower` |
| `TOWER_LANGSMITH_ENABLE` | Enable remote LangSmith | `0` |
| `LANGSMITH_API_KEY` | LangSmith API key | (empty) |

## How It Works

1. Records start time (UTC ISO + epoch)
2. Calls `tower/scripts/tower_run.sh` with provided args
3. After run completes, discovers the newest run directory under:
   - `tower/artifacts/YYYY-MM-DD/<CARD>/run_*/`
4. Loads `run_context.json` and `run_summary.json` from run dir
5. Emits LangSmith trace (local + optionally remote)
6. Logs to MLflow (if installed)
7. Returns the underlying command's exit code

## Trace Events

The bridge emits START and END events:

```json
{
  "timestamp": "2026-01-17T10:30:00Z",
  "run_id": "run_20260117_001",
  "card_id": "CARD-001",
  "session": "apps_dev1",
  "model": "claude_opus",
  "command": "bash tower/scripts/tower_dashboard.sh",
  "status": "START",
  "addon": {
    "langsmith": {"local": true, "remote_attempted": false, "remote_ok": true},
    "mlflow": {"attempted": true, "ok": true}
  }
}
```

## Troubleshooting

### "No run directory found"

The bridge looks for run directories in both today's UTC date and local date folders. If your run straddles midnight, check both:
- `tower/artifacts/2026-01-17/<CARD>/`
- `tower/artifacts/2026-01-18/<CARD>/`

### "mlflow not installed"

Install into your addons venv:
```bash
source tower/.venv_addons/bin/activate
pip install mlflow
```

### "langsmith adapter missing"

Run the addons scaffold first to create the adapter:
```bash
# The adapter should be at:
tower/addons/langsmith/langsmith_adapter.py
```

### Exit codes

- The bridge preserves the underlying command's exit code
- Addon failures (MLflow/LangSmith) do NOT change the exit code
- Addon failures are printed as warnings
