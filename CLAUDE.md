# CLAUDE.md — Tower Project (Python)

## Project Overview
Tower is a card-based task/gate management system with bash automation scripts. Uses `status.json` for state, Python for validation logic, and bash scripts for orchestration.

## Critical Warnings
- **`status.json` `cards` is an ARRAY** of objects, NOT a dict — scripts must iterate, not key-index
- **Git Bash on Windows** needs `to_win_path()` for Python; heredocs must use `<< 'EOF'` (quoted) + env vars
- **Severity enum comparison**: string `.value` fails ("low">"high" alphabetically) — use ordinal mapping
- **`evaluate_card_gates()` echo lines** must go to stderr (`>&2`) to avoid corrupting JSON capture
- **Temp files** need PID suffix (`.$$`) to prevent concurrent collision
- **`set -e` + `result=$(fn_returning_nonzero)`** kills script — must use `&& true` to suppress
- **`local` keyword** only valid inside functions — using it at top-level produces bash error
- **Python `isinstance(True, int)`** is True (bool subclasses int) — exclude explicitly for type validation

## Key Files
- `tower_run.sh`, `tower_gatecheck.sh`, `merge_gold.sh`, `tower_proofpack.sh` — bash scripts
- `status.json` — state file (cards array)
- `integration_test.py` — tests including severity ordinal regression

## Do NOT
- Index `cards` by key (it's an array, not a dict)
- Use `local` at top-level in bash scripts
- Echo to stdout inside functions whose output is captured as JSON
- Compare severity strings alphabetically

## Workflow Rules (from 1,600+ message usage analysis)

### Test-First Verification (CRITICAL)
- **Never say "done" without test verification.** After any round of fixes, run the full test suite and report pass/fail counts before declaring complete.
- **Test each feature immediately upon implementation** — do not batch test runs at the end.
- If fixes introduce new failures, fix those too before declaring done. Track fixes with IDs (e.g., P0-1, P1-3).

### Data Model Verification Before Implementation
- **Before implementing any feature**, grep the codebase for all data objects/structures related to that feature. Verify actual property names, types, and where they are set.
- **Never guess property names or element IDs.** Confirm properties exist in the actual data model before writing access paths.

### Context Persistence
- **Save review findings to files** (e.g., `review-findings.md`) so they persist across sessions.
- **Never report features as "missing" without evidence.** Search thoroughly with Grep before claiming a feature is absent.

### Data Integrity
Never fabricate or hallucinate identifiers (NCT IDs, DOIs, trial names, PMIDs). If you don't have the real identifier, say so and ask the user to provide it. Always verify identifiers against existing data files before using them in configs or gold standards.

### Multi-Persona Reviews
When running multi-persona reviews, run agents sequentially (not in parallel) to avoid rate limits and empty agent outputs. If an agent returns empty output, immediately retry it before moving on. Never launch more than 2 sub-agents simultaneously.

### Fix Completeness
When asked to "fix all issues", fix ALL identified issues in a single pass — do not stop partway. After applying fixes, re-run the relevant tests/validation before reporting completion. If fixes introduce new failures, fix those too before declaring done.

### Scope Discipline
Stay focused on the specific files and scope the user requests. Do not survey or analyze files outside the stated scope. When editing files, triple-check you are editing the correct file path — never edit a stale copy or wrong directory.

### Regression Prevention
Before applying optimization changes to extraction or analysis pipelines, save a snapshot of current accuracy metrics. After each change, compare against the snapshot. If any trial/metric regresses by more than 2%, immediately rollback and try a different approach. Never apply aggressive heuristics without isolated testing first.
