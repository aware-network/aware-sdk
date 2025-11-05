from __future__ import annotations

from pathlib import Path

from aware_test_runner.config import load_manifest
from aware_test_runner.core.discovery import TestSuiteDiscovery


def _load_oss_manifest() -> TestSuiteDiscovery:
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = repo_root / "tools" / "test-runner" / "configs" / "manifests" / "oss" / "manifest.json"
    manifest = load_manifest(manifest_file=str(manifest_path))
    return TestSuiteDiscovery(str(repo_root), manifest)


def test_tools_category_discovery() -> None:
    discovery = _load_oss_manifest()

    categories = discovery.available_categories()
    assert "tools" in categories

    suites = discovery.get_suites_by_category("tools")
    assert "test-runner" in suites
    assert suites["test-runner"].path.endswith("test-runner/tests")


def test_lib_category_alias() -> None:
    discovery = _load_oss_manifest()

    lib_suites = discovery.get_suites_by_category("lib")
    libs_suites = discovery.get_suites_by_category("libs")
    assert lib_suites
    assert lib_suites.keys() == libs_suites.keys()
