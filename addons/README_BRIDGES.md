# Tower Addons Bridges Pack (Optional)

These are OPTIONAL integration bridges. Base Tower remains file-based + bash scripts.
Nothing here modifies Tower core scripts or your application code.

## Prereqs
These bridges assume you already have a Python venv at:
- tower/.venv_addons

If not, create it (copy/paste):
```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip && \
python3 -m venv tower/.venv_addons && \
. tower/.venv_addons/bin/activate && \
python -m pip install -U pip setuptools wheel && \
python -m pip install -r tower/addons/requirements_addons.txt && \
deactivate
```

If you also created the "Addons Plus" requirements files:
- tower/addons/requirements_orchestration.txt
- tower/addons/requirements_tracing.txt
- tower/addons/requirements_evals.txt

Install them similarly, e.g.:
```bash
. tower/.venv_addons/bin/activate && python -m pip install -r tower/addons/requirements_orchestration.txt && deactivate
```

## 1) MLflow: Log a Tower run directory
Purpose: take a single Tower run folder and log it as an MLflow run (params/metrics/artifacts).
This uses a LOCAL file store by default at: tower/addons/mlruns/

Example:
```bash
. tower/.venv_addons/bin/activate
python tower/addons/mlflow_log_run.py --run_dir tower/artifacts/2026-01-16/CARD-001/run_20260116_123000_abcd1234
deactivate
```

Notes:
- No server required. MLflow UI is optional:
```bash
. tower/.venv_addons/bin/activate && mlflow ui --backend-store-uri tower/addons/mlruns && deactivate
```

## 2) Prefect: Run Tower scripts as a flow (optional scheduler)
Purpose: wrap existing Tower scripts (validate/dashboard/night) in a Prefect flow.
No Tower scripts are changed; Prefect just calls them.

Examples:
```bash
. tower/.venv_addons/bin/activate
python tower/addons/prefect_tower_flow.py --task validate
python tower/addons/prefect_tower_flow.py --task dashboard
python tower/addons/prefect_tower_flow.py --task night
deactivate
```

## 3) Dagster: Minimal definitions
Purpose: provide a Dagster repo that shells out to Tower scripts.
This does NOT start a server. It just provides definitions you can run if you want.

Examples:
```bash
. tower/.venv_addons/bin/activate
python -c "from tower.addons.dagster.definitions import defs; print(defs)"
deactivate
```

## 4) LangSmith: Command wrapper (optional tracing)
Purpose: wrap an arbitrary command so it can be traced IF you set env vars yourself.
This file does not store keys or start services.

Example:
```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="..."      # keep in your shell history discipline
export LANGSMITH_PROJECT="tower"
. tower/.venv_addons/bin/activate
python tower/addons/langsmith_cmd_wrapper.py --name "tower_validate" -- bash tower/scripts/validate_all.sh
deactivate
```

## Daily use (activate/deactivate)
```bash
. tower/.venv_addons/bin/activate
# ...run things...
deactivate
```

## Troubleshooting
Recreate venv:
```bash
rm -rf tower/.venv_addons
python3 -m venv tower/.venv_addons
. tower/.venv_addons/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -r tower/addons/requirements_addons.txt
deactivate
```

Verify imports:
```bash
. tower/.venv_addons/bin/activate
python -c "import jsonschema; print('jsonschema ok')"
python -c "import mlflow; print('mlflow ok')"
python -c "import prefect; print('prefect ok')"
deactivate
```
