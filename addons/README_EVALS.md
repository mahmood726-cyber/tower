# Tower Addons: Evals (Optional)

## Purpose

Optional evaluation harness for Tower. Base Tower remains artifact-first.
- **OpenAI Evals** - Open-source evaluation framework
- **OpenAI Platform Evals** - API-based grading (alternative)

---

## Install (WSL2 one-liner)

```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip && \
[ -d tower/.venv_addons ] || python3 -m venv tower/.venv_addons && \
. tower/.venv_addons/bin/activate && \
python -m pip install -U pip setuptools wheel && \
python -m pip install -r tower/addons/requirements_evals.txt && \
deactivate
```

---

## Path 1: Open-Source OpenAI Evals (oaieval)

The `evals` package provides the open-source evaluation framework.

### Example usage
```bash
. tower/.venv_addons/bin/activate

# List available evals
oaieval --help

# Run an eval (example form)
oaieval <model> <eval_name>

# Example with GPT-4
oaieval gpt-4 match

deactivate
```

Notes:
- Requires OPENAI_API_KEY environment variable
- See: https://github.com/openai/evals
- No servers started automatically

---

## Path 2: OpenAI Platform Evals/Grading

Alternatively, use OpenAI's API-based evaluation and grading:
- Create evals via the OpenAI dashboard
- Use the API for automated grading

```python
from openai import OpenAI
client = OpenAI()  # uses OPENAI_API_KEY from env

# Example: use completions for grading
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Grade this response..."}]
)
```

Notes:
- No API keys stored in Tower
- Set OPENAI_API_KEY in your environment
- No services started automatically

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
python -m pip install -r tower/addons/requirements_evals.txt
deactivate
```

### Verify imports
```bash
. tower/.venv_addons/bin/activate
python -c "import openai; print('openai', openai.__version__)"
python -c "import evals; print('evals ok')"
deactivate
```

### Check oaieval CLI
```bash
. tower/.venv_addons/bin/activate
oaieval --help
deactivate
```
