# Tower Prefect Addon

Optional Prefect flows for Tower orchestration. Wraps existing Tower scripts without modifying them.

## Installation

```bash
# Activate your addons virtualenv
source tower/.venv_addons/bin/activate

# Install Prefect
pip install prefect
```

## Configuration

Copy and edit the env file:

```bash
cp tower/addons/prefect/prefect.env.example tower/addons/prefect/.env
export $(cat tower/addons/prefect/.env | grep -v '^#' | xargs)
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PREFECT_API_URL` | Prefect API URL (blank = local ephemeral) | (empty) |
| `TOWER_PREFECT_ENABLE` | Enable Prefect flows (1/0) | `0` |

## Available Flows

| Flow | Description | Script Called |
|------|-------------|---------------|
| `tower_night_runner` | Nightly batch processing | `tower/scripts/night_runner.sh` |
| `tower_watchdog` | Health monitoring | `tower/scripts/tower_watchdog.sh` |
| `tower_pc_router` | PC job routing | `tower/scripts/pc_job_router.sh` |

## Usage

### Run Locally (No Server Required)

```bash
# Run a specific flow
python3 tower/addons/prefect/prefect_flows.py --run night
python3 tower/addons/prefect/prefect_flows.py --run watchdog
python3 tower/addons/prefect/prefect_flows.py --run router

# List available flows
python3 tower/addons/prefect/prefect_flows.py --list
```

### Run Outputs

Each flow creates artifacts under:
```
tower/addons/prefect/runs/YYYY-MM-DD/<flow_name>_<run_id>.json
tower/addons/prefect/runs/YYYY-MM-DD/<flow_name>_<run_id>.out
tower/addons/prefect/runs/YYYY-MM-DD/<flow_name>_<run_id>.err
```

### Optional: Prefect Server

Prefect server is NOT required for local runs. If you want the UI:

```bash
# Start server (optional)
prefect server start

# Then set API URL
export PREFECT_API_URL=http://127.0.0.1:4200/api
```

## Flow Details

### tower_night_runner

Runs the nightly batch processing flow:
- Executes `tower/scripts/night_runner.sh`
- Captures stdout/stderr
- Records duration and exit code

### tower_watchdog

Monitors Tower health:
- Executes `tower/scripts/tower_watchdog.sh`
- Checks control file validity
- Reports anomalies

### tower_pc_router

Routes jobs to available PCs:
- Executes `tower/scripts/pc_job_router.sh`
- Distributes work across machines
- Balances load

## Troubleshooting

**"prefect not installed"**: Install with `pip install prefect`

**"flow not found"**: Check available flows with `--list`

**"script not found"**: Ensure Tower skeleton is properly installed

**"permission denied"**: Make scripts executable with `chmod +x tower/scripts/*.sh`
