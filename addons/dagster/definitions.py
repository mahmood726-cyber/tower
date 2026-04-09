"""
Minimal Dagster definitions for Tower (optional).
This shells out to Tower scripts. It does not start a server, and it does not modify Tower.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

try:
    from dagster import Definitions, asset  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "Dagster is not installed. Activate tower/.venv_addons and install requirements_orchestration.txt"
    ) from e


REPO_ROOT = Path.cwd().resolve()
TOWER_SCRIPTS = REPO_ROOT / "tower" / "scripts"


def _bash(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Missing script: {path}")
    subprocess.check_call(["bash", path.as_posix()])


@asset
def tower_validate() -> None:
    _bash(TOWER_SCRIPTS / "validate_all.sh")


@asset
def tower_dashboard() -> None:
    _bash(TOWER_SCRIPTS / "tower_dashboard.sh")


@asset
def tower_night() -> None:
    # Optional: only works if your skeleton created it
    _bash(TOWER_SCRIPTS / "night_runner.sh")


defs = Definitions(assets=[tower_validate, tower_dashboard, tower_night])
