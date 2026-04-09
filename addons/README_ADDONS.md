# Tower Addons

## Purpose

These are **optional** integrations for Tower:
- **Prefect** - Local workflow orchestration
- **MLflow** - Run tracking and artifacts
- **jsonschema** - JSON validation

Keep base Tower minimal. Install only what you need.

---

## Install (WSL2 Ubuntu one-liner)

```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip && \
python3 -m venv tower/.venv_addons && \
. tower/.venv_addons/bin/activate && \
python -m pip install -U pip setuptools wheel && \
python -m pip install -r tower/addons/requirements_addons.txt && \
deactivate
```

---

## Daily Use

Activate:
```bash
. tower/.venv_addons/bin/activate
```

Deactivate:
```bash
deactivate
```

---

## Troubleshooting

### Remove and recreate venv
```bash
rm -rf tower/.venv_addons
python3 -m venv tower/.venv_addons
. tower/.venv_addons/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -r tower/addons/requirements_addons.txt
deactivate
```

### Verify installs
```bash
. tower/.venv_addons/bin/activate
python -c "import prefect; print('prefect', prefect.__version__)"
python -c "import mlflow; print('mlflow', mlflow.__version__)"
python -c "import jsonschema; print('jsonschema', jsonschema.__version__)"
deactivate
```

### MLflow UI (local, no server required)
```bash
. tower/.venv_addons/bin/activate
cd tower/addons/mlflow/state
mlflow ui
# Open http://localhost:5000
```

Note: MLflow UI runs locally on demand. Nothing starts automatically.
