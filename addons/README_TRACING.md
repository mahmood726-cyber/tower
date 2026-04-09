# Tower Addons: Tracing (Optional)

## Purpose

Optional tracing integrations for Tower. Base Tower stays file-based.
- **LangSmith** - Hosted LLM tracing from LangChain
- **Langfuse** - Open-source LLM observability (self-host or cloud)

---

## Install (WSL2 one-liner)

```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip && \
[ -d tower/.venv_addons ] || python3 -m venv tower/.venv_addons && \
. tower/.venv_addons/bin/activate && \
python -m pip install -U pip setuptools wheel && \
python -m pip install -r tower/addons/requirements_tracing.txt && \
deactivate
```

---

## LangSmith Setup (no code changes)

Set environment variables before running your Tower commands:
```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="your_api_key_here"
export LANGSMITH_PROJECT="tower"
```

Notes:
- Uses hosted LangSmith at https://smith.langchain.com
- No services started automatically
- Get your API key from the LangSmith dashboard

---

## Langfuse (Optional)

Langfuse requires a backend (self-hosted or cloud):
```bash
export LANGFUSE_PUBLIC_KEY="your_public_key"
export LANGFUSE_SECRET_KEY="your_secret_key"
export LANGFUSE_HOST="https://cloud.langfuse.com"  # or your self-hosted URL
```

Notes:
- Self-host docs: https://langfuse.com/docs/deployment
- Cloud: https://cloud.langfuse.com
- No services started automatically by Tower

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
python -m pip install -r tower/addons/requirements_tracing.txt
deactivate
```

### Verify imports
```bash
. tower/.venv_addons/bin/activate
python -c "import langsmith; print('langsmith', langsmith.__version__)"
python -c "import langfuse; print('langfuse', langfuse.version)"
deactivate
```
