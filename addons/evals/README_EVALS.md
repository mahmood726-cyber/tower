# Tower Evals Pack

Nightly regression tests with scoring for Tower. Command-driven, model-agnostic evaluation suite.

## Overview

The Evals Pack provides:
- **Test cases**: JSON files defining commands to run and expected outcomes
- **Test runner**: Python script that executes cases and computes scores
- **Trend tracking**: Append-only CSV for tracking score over time

## Installation

No additional dependencies required. Uses Python 3 standard library.

Optional for schema validation:
```bash
pip install jsonschema
```

## Usage

### List Available Cases

```bash
python3 tower/addons/evals/run_evals.py --list
```

### Run All Tests

```bash
python3 tower/addons/evals/run_evals.py --all
```

### Run Specific Test

```bash
python3 tower/addons/evals/run_evals.py --case EV-000
```

### Custom Output Directory

```bash
python3 tower/addons/evals/run_evals.py --all --outdir ./my_evals
```

### Fail Fast (Stop on First Failure)

```bash
python3 tower/addons/evals/run_evals.py --all --fail-fast
```

## Test Case Format

Test cases are JSON files in `tower/addons/evals/cases/`:

```json
{
  "case_id": "EV-000",
  "title": "Validate base Tower control files",
  "command": "bash tower/scripts/validate_all.sh",
  "cwd": null,
  "timeout_seconds": 900,
  "expected_exit_code": 0,
  "checks": [],
  "points": 3
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `case_id` | string | Unique identifier (e.g., EV-000) |
| `title` | string | Human-readable description |
| `command` | string | Command to execute |
| `cwd` | string/null | Working directory (null = repo root) |
| `timeout_seconds` | int | Maximum execution time |
| `expected_exit_code` | int | Expected return code (0 = success) |
| `checks` | array | Additional validation checks |
| `points` | int | Points for passing (default 1) |

### Check Types

- `file_exists`: Check if file exists after run
- `json_schema`: Validate output against JSON schema
- `regex_in_file`: Check for pattern in output file
- `sha256_matches`: Verify file hash

## Output Files

Each run creates:
```
tower/addons/evals/artifacts/YYYY-MM-DD/run_<run_id>/
  evals_report.json    # Detailed per-test results
  evals_score.json     # Summary score
  case_EV-000_stdout.log
  case_EV-000_stderr.log
  ...
```

### evals_report.json

```json
{
  "run_id": "20260117103045_a1b2c3",
  "created_at": "2026-01-17T10:30:45Z",
  "cases": [
    {
      "case_id": "EV-000",
      "title": "Validate base Tower control files",
      "status": "PASS",
      "exit_code": 0,
      "duration_sec": 12.5,
      "points": 3,
      "stdout_path": "case_EV-000_stdout.log",
      "stderr_path": "case_EV-000_stderr.log"
    }
  ],
  "summary": {
    "passed": 3,
    "failed": 0,
    "skipped": 0,
    "total_points": 7,
    "max_points": 7,
    "score_pct": 100.0
  }
}
```

### evals_score.csv (Trend Tracking)

Appended to `tower/addons/evals/artifacts/evals_score.csv`:

```csv
timestamp,run_id,score_pct,total_points,max_points,passed,failed,skipped
2026-01-17T10:30:45Z,20260117103045_a1b2c3,100.0,7,7,3,0,0
```

## Default Test Cases

| Case ID | Description | Points |
|---------|-------------|--------|
| EV-000 | Validate base Tower control files | 3 |
| EV-010 | Gatecheck smoke test | 2 |
| EV-020 | Proofpack smoke test | 2 |

## Adding Custom Cases

Create a new JSON file in `tower/addons/evals/cases/`:

```json
{
  "case_id": "EV-100",
  "title": "My custom test",
  "command": "bash my_test.sh",
  "timeout_seconds": 300,
  "expected_exit_code": 0,
  "points": 1
}
```

## Shell Wrapper

For convenience, use the shell wrapper:

```bash
bash tower/addons/evals/run_evals.sh
```

## Troubleshooting

**"Script not found"**: Ensure Tower scripts exist. Missing scripts cause SKIP (not FAIL).

**"Timeout"**: Increase `timeout_seconds` in case file.

**"Permission denied"**: Make scripts executable: `chmod +x tower/scripts/*.sh`

**"jsonschema not installed"**: Cases still run, but schema validation is skipped.
