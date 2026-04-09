# Tower MLflow Addon

Optional MLflow integration for Tower experiment tracking. Uses local file-based tracking by default.

## Installation

```bash
# Activate your addons virtualenv
source tower/.venv_addons/bin/activate

# Install MLflow
pip install mlflow
```

## Configuration

Copy and edit the env file:

```bash
cp tower/addons/mlflow/mlflow.env.example tower/addons/mlflow/.env
export $(cat tower/addons/mlflow/.env | grep -v '^#' | xargs)
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MLFLOW_TRACKING_URI` | Tracking store location | `file:./tower/addons/mlflow/mlruns` |
| `MLFLOW_EXPERIMENT_NAME` | Default experiment name | `tower` |

## Usage

### Run Wrapper

Wrap any command with MLflow logging:

```bash
python3 tower/addons/mlflow/mlflow_run_wrapper.py \
  --name "tower_dashboard" \
  --cmd "bash tower/scripts/tower_dashboard.sh" \
  --card CARD-001 \
  --model claude_opus \
  --session apps_dev1
```

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--name` | Run name/label | Yes |
| `--cmd` | Command to execute | Yes |
| `--card` | Card ID | No |
| `--model` | Model name | No |
| `--session` | Session name | No |
| `--tags` | Comma-separated tags | No |

### Logged Data

The wrapper logs:
- **Parameters**: card_id, session, model, command, cwd
- **Metrics**: exit_code, duration_sec
- **Artifacts**: stdout.log, stderr.log, wrapper_run.json

### Run Outputs

Wrapper creates local files under:
```
tower/addons/mlflow/runs/YYYY-MM-DD/run_<run_id>/
  stdout.log
  stderr.log
  wrapper_run.json
```

MLflow tracking data goes to:
```
tower/addons/mlflow/mlruns/
```

## Optional: MLflow UI

To view experiments in the MLflow UI (optional, not auto-started):

```bash
mlflow ui \
  --backend-store-uri file:$(pwd)/tower/addons/mlflow/mlruns \
  --host 127.0.0.1 \
  --port 5000
```

Then open http://127.0.0.1:5000 in your browser.

## Troubleshooting

**"mlflow not installed"**: Install with `pip install mlflow`

**"No experiments found"**: Run some commands with the wrapper first

**"Permission denied"**: Check mlruns directory permissions

**"Tracking URI not found"**: Ensure MLFLOW_TRACKING_URI points to valid path
