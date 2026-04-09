# Tower Addons: Orchestration (Optional)

## Purpose

Optional orchestrator for Tower. Base Tower works with bash scripts.
- **Dagster** - Data orchestration platform with asset-based pipelines

---

## Install (WSL2 one-liner)

```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip && \
[ -d tower/.venv_addons ] || python3 -m venv tower/.venv_addons && \
. tower/.venv_addons/bin/activate && \
python -m pip install -U pip setuptools wheel && \
python -m pip install -r tower/addons/requirements_orchestration.txt && \
deactivate
```

---

## Hello Dagster (no server)

Verify installation without starting a server:
```bash
. tower/.venv_addons/bin/activate

# Check Dagster CLI
dagster --version

# Verify Python imports
python -c "from dagster import asset, Definitions; print('dagster ok')"

deactivate
```

### Run assets directly (no UI)
```bash
. tower/.venv_addons/bin/activate
python -c "
from dagster import asset, materialize

@asset
def hello_tower():
    return 'Hello from Tower + Dagster'

result = materialize([hello_tower])
print('Materialized:', result.success)
"
deactivate
```

Notes:
- No server started automatically
- Optional UI: `dagster dev` (starts local webserver on port 3000)
- See: https://docs.dagster.io

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

### Recreate venv
```bash
rm -rf tower/.venv_addons
python3 -m venv tower/.venv_addons
. tower/.venv_addons/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -r tower/addons/requirements_orchestration.txt
deactivate
```

### Verify imports
```bash
. tower/.venv_addons/bin/activate
python -c "import dagster; print('dagster', dagster.__version__)"
python -c "from dagster import asset, Definitions; print('dagster imports ok')"
deactivate
```
