"""Pytest contracts for the Tower QA integration suite."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "addons" / "qa" / "scripts"))

from integration_test import IntegrationTestSuite  # noqa: E402


def _assert_suite_check(method_name: str) -> None:
    suite = IntegrationTestSuite(quick=True)
    passed, message = getattr(suite, method_name)()
    assert passed, message


def test_manifest_exists() -> None:
    _assert_suite_check("test_manifest_exists")


def test_manifest_addon_paths_exist() -> None:
    _assert_suite_check("test_manifest_addon_paths_exist")


def test_schemas_are_valid_json() -> None:
    _assert_suite_check("test_schemas_valid_json")


def test_schemas_have_required_fields() -> None:
    _assert_suite_check("test_schemas_have_required_fields")
