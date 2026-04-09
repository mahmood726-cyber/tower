#!/usr/bin/env python3
"""
Tower Evals Runner

Executes test cases and computes scores.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
CASES_DIR = SCRIPT_DIR / "cases"
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
TOWER_ROOT = SCRIPT_DIR.parent.parent
REPO_ROOT = TOWER_ROOT.parent


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_run_id() -> str:
    ts = _now_utc().strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{ts}_{suffix}"


def _load_cases() -> List[Dict[str, Any]]:
    """Load all test cases from cases directory."""
    cases = []

    if not CASES_DIR.exists():
        return cases

    for case_file in sorted(CASES_DIR.glob("*.json")):
        try:
            with open(case_file, encoding="utf-8") as f:
                case = json.load(f)
                case["_file"] = str(case_file)
                cases.append(case)
        except Exception as e:
            print(f"WARNING: Failed to load {case_file}: {e}", file=sys.stderr)

    return cases


def _validate_schema(data: Dict, schema_name: str) -> bool:
    """Validate data against schema (if jsonschema available)."""
    try:
        import jsonschema

        schema_path = TOWER_ROOT / "qa" / "schemas" / schema_name
        if not schema_path.exists():
            return True  # No schema = pass

        with open(schema_path) as f:
            schema = json.load(f)

        jsonschema.validate(data, schema)
        return True
    except ImportError:
        return True  # No jsonschema = skip validation
    except Exception:
        return False


def _run_case(
    case: Dict[str, Any],
    run_dir: Path,
    fail_fast: bool = False
) -> Dict[str, Any]:
    """
    Run a single test case.

    Returns result dict with status, exit_code, duration, etc.
    """
    case_id = case.get("case_id", "unknown")
    title = case.get("title", "Untitled")
    command = case.get("command", "")
    cwd = case.get("cwd")
    timeout = case.get("timeout_seconds", 300)
    expected_exit = case.get("expected_exit_code", 0)
    points = case.get("points", 1)

    stdout_file = run_dir / f"case_{case_id}_stdout.log"
    stderr_file = run_dir / f"case_{case_id}_stderr.log"

    result = {
        "case_id": case_id,
        "title": title,
        "command": command,
        "status": "PENDING",
        "exit_code": None,
        "expected_exit_code": expected_exit,
        "duration_sec": 0,
        "points_earned": 0,
        "points_max": points,
        "stdout_path": str(stdout_file.name),
        "stderr_path": str(stderr_file.name),
        "reason": ""
    }

    # Determine working directory (with path traversal protection)
    if cwd:
        work_dir = Path(cwd)
        if not work_dir.is_absolute():
            work_dir = REPO_ROOT / cwd
        # Security: Ensure resolved path is within REPO_ROOT
        try:
            work_dir = work_dir.resolve()
            work_dir.relative_to(REPO_ROOT.resolve())
        except ValueError:
            result["status"] = "SKIP"
            result["reason"] = f"Security: cwd '{cwd}' escapes repository root"
            stdout_file.write_text(f"SKIP: {result['reason']}\n")
            stderr_file.write_text("")
            return result
    else:
        work_dir = REPO_ROOT

    # Check if command references a script that doesn't exist
    if command.startswith("bash "):
        script_path = command.split()[1]
        full_script = REPO_ROOT / script_path
        if not full_script.exists():
            result["status"] = "SKIP"
            result["reason"] = f"Script not found: {script_path}"
            # Write empty log files
            stdout_file.write_text(f"SKIP: {result['reason']}\n")
            stderr_file.write_text("")
            return result

    print(f"  Running {case_id}: {title}...", end=" ", flush=True)

    start_time = _now_utc()

    try:
        with open(stdout_file, "w") as fout, open(stderr_file, "w") as ferr:
            proc = subprocess.run(
                command,
                shell=True,
                stdout=fout,
                stderr=ferr,
                cwd=str(work_dir),
                timeout=timeout
            )

        end_time = _now_utc()
        duration = (end_time - start_time).total_seconds()

        result["exit_code"] = proc.returncode
        result["duration_sec"] = round(duration, 2)

        if proc.returncode == expected_exit:
            result["status"] = "PASS"
            result["points_earned"] = points
            print("PASS")
        else:
            result["status"] = "FAIL"
            result["reason"] = f"Exit {proc.returncode}, expected {expected_exit}"
            print(f"FAIL (exit {proc.returncode})")

    except subprocess.TimeoutExpired:
        result["status"] = "FAIL"
        result["reason"] = f"Timeout after {timeout}s"
        stdout_file.write_text(f"TIMEOUT after {timeout}s\n")
        stderr_file.write_text("")
        print(f"TIMEOUT ({timeout}s)")

    except Exception as e:
        result["status"] = "ERROR"
        result["reason"] = str(e)
        stdout_file.write_text(f"ERROR: {e}\n")
        stderr_file.write_text("")
        print(f"ERROR: {e}")

    return result


def run_evals(
    cases: Optional[List[str]] = None,
    outdir: Optional[Path] = None,
    fail_fast: bool = False
) -> Dict[str, Any]:
    """
    Run evaluation cases and return results.

    Args:
        cases: List of case IDs to run, or None for all
        outdir: Output directory (default: artifacts/YYYY-MM-DD/run_<id>)
        fail_fast: Stop on first failure

    Returns:
        Results dict with cases, summary, paths
    """
    all_cases = _load_cases()

    if not all_cases:
        print("No test cases found in", CASES_DIR)
        return {"error": "No test cases found"}

    # Filter cases if specific ones requested
    if cases:
        filtered = [c for c in all_cases if c.get("case_id") in cases]
        if not filtered:
            print(f"No matching cases found for: {cases}")
            return {"error": "No matching cases"}
        all_cases = filtered

    # Create run directory
    run_id = _generate_run_id()
    if outdir:
        run_dir = Path(outdir)
    else:
        today = _now_utc().strftime("%Y-%m-%d")
        run_dir = ARTIFACTS_DIR / today / f"run_{run_id}"

    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(all_cases)} test case(s)")
    print(f"Run ID: {run_id}")
    print(f"Output: {run_dir}")
    print()

    # Run cases
    results = []
    for case in all_cases:
        result = _run_case(case, run_dir, fail_fast)
        results.append(result)

        if fail_fast and result["status"] in ("FAIL", "ERROR"):
            print("\nFail-fast: stopping on first failure")
            break

    # Compute summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    total_points = sum(r["points_earned"] for r in results)
    max_points = sum(r["points_max"] for r in results)
    score_pct = (total_points / max_points * 100) if max_points > 0 else 0

    summary = {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total_points": total_points,
        "max_points": max_points,
        "score_pct": round(score_pct, 1)
    }

    # Build report
    report = {
        "run_id": run_id,
        "created_at": _now_utc().isoformat(),
        "cases": results,
        "summary": summary
    }

    # Write report
    report_file = run_dir / "evals_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    # Write score summary
    score_file = run_dir / "evals_score.json"
    score_data = {
        "run_id": run_id,
        "timestamp": _now_utc().isoformat(),
        "score_pct": summary["score_pct"],
        "total_points": total_points,
        "max_points": max_points,
        "passed": passed,
        "failed": failed,
        "skipped": skipped
    }
    with open(score_file, "w") as f:
        json.dump(score_data, f, indent=2)

    # Append to trend CSV
    trend_file = ARTIFACTS_DIR / "evals_score.csv"
    trend_exists = trend_file.exists()

    with open(trend_file, "a", newline="") as f:
        writer = csv.writer(f)
        if not trend_exists:
            writer.writerow([
                "timestamp", "run_id", "score_pct", "total_points",
                "max_points", "passed", "failed", "skipped"
            ])
        writer.writerow([
            _now_utc().isoformat(), run_id, summary["score_pct"],
            total_points, max_points, passed, failed, skipped
        ])

    # Print summary
    print()
    print("=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"SCORE: {score_pct:.1f}% ({total_points}/{max_points} points)")
    print(f"Report: {report_file}")
    print("=" * 50)

    return report


def list_cases():
    """List available test cases."""
    cases = _load_cases()

    if not cases:
        print("No test cases found in", CASES_DIR)
        return

    print("Available test cases:")
    print()
    print(f"{'ID':<10} {'Points':<8} {'Title'}")
    print("-" * 60)

    for case in cases:
        case_id = case.get("case_id", "unknown")
        points = case.get("points", 1)
        title = case.get("title", "Untitled")
        print(f"{case_id:<10} {points:<8} {title}")

    print()
    print(f"Total: {len(cases)} cases, {sum(c.get('points', 1) for c in cases)} points")


def main() -> int:
    parser = argparse.ArgumentParser(description="Tower Evals Runner")
    parser.add_argument("--list", action="store_true", help="List available cases")
    parser.add_argument("--all", action="store_true", help="Run all cases")
    parser.add_argument("--case", action="append", help="Run specific case(s)")
    parser.add_argument("--outdir", help="Custom output directory")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Stop on first failure")
    parser.add_argument("--json-out", help="Write results to JSON file")

    args = parser.parse_args()

    if args.list:
        list_cases()
        return 0

    if args.all:
        cases = None
    elif args.case:
        cases = args.case
    else:
        parser.print_help()
        return 0

    outdir = Path(args.outdir) if args.outdir else None
    results = run_evals(cases=cases, outdir=outdir, fail_fast=args.fail_fast)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(results, f, indent=2)

    # Exit with non-zero if any failures
    if results.get("error"):
        return 1
    if results.get("summary", {}).get("failed", 0) > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
