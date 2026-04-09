# Tower LangSmith Addon

Optional tracing adapter for Tower. Supports local-only traces and optional remote LangSmith integration.

## Modes

1. **Local trace only** (default): Writes JSON lines to `tower/addons/langsmith/traces/<YYYY-MM-DD>.jsonl`
2. **Remote tracing**: If `langsmith` is installed AND `LANGSMITH_API_KEY` is set, also sends to LangSmith

## Installation

```bash
# Optional - only needed for remote tracing
pip install langsmith
```

## Configuration

Copy and edit the env file:

```bash
cp tower/addons/langsmith/langsmith.env.example tower/addons/langsmith/.env
# Edit .env with your settings
export $(cat tower/addons/langsmith/.env | grep -v '^#' | xargs)
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LANGSMITH_API_KEY` | API key for remote tracing | (empty) |
| `LANGSMITH_PROJECT` | Project name in LangSmith | `tower` |
| `LANGSMITH_ENDPOINT` | LangSmith API endpoint | `https://api.smith.langchain.com` |
| `TOWER_LANGSMITH_ENABLE` | Enable remote tracing (1/0) | `0` |

## Usage

### Python API

```python
from langsmith_adapter import emit_trace, emit_trace_remote

# Always writes locally
emit_trace({
    "run_id": "run_20260117_001",
    "card_id": "CARD-001",
    "status": "START",
    "command": "bash tower/scripts/validate_all.sh"
})

# Remote only if configured
emit_trace_remote({
    "run_id": "run_20260117_001",
    "status": "END",
    "exit_code": 0,
    "duration_sec": 12.5
})
```

### CLI

```bash
# Emit a trace event
python3 tower/addons/langsmith/trace_local.py --event '{"run_id":"run_001","status":"START"}'
```

## Event Schema

```json
{
  "timestamp": "2026-01-17T10:30:00Z",
  "run_id": "run_20260117_001",
  "card_id": "CARD-001",
  "session": "apps_dev1",
  "model": "claude_opus",
  "command": "bash tower/scripts/validate_all.sh",
  "status": "START|END|INFO|ERROR",
  "exit_code": 0,
  "duration_sec": 12.5,
  "paths": ["tower/artifacts/2026-01-17/CARD-001/run_001/"],
  "tags": ["nightly", "validation"]
}
```

## Trace Files

Local traces are stored at:
```
tower/addons/langsmith/traces/
  2026-01-17.jsonl
  2026-01-18.jsonl
  ...
```

Each file contains one JSON object per line (JSONL format).

## Troubleshooting

**"langsmith not installed"**: Only needed for remote tracing. Local traces work without it.

**"LANGSMITH_API_KEY not set"**: Set the environment variable for remote tracing.

**"Remote trace failed"**: Check API key and network. Local traces continue regardless.
