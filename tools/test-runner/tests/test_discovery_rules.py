from __future__ import annotations

import json
from pathlib import Path

import pytest

from aware_test_runner.config import load_manifest
from aware_test_runner.core.discovery import TestSuiteDiscovery


def _write_manifest(root: Path, manifest_dir: Path) -> None:
    manifest_dir.mkdir(parents=True, exist_ok=True)

    manifest_payload = {
        "id": "oss-test",
        "discovery": [
            {
                "id": "libraries",
                "category": "lib",
                "category_aliases": ["libs"],
                "type": "package",
                "root": "libs",
                "max_depth": 1,
                "tests_dir": "tests",
                "name": {
                    "strategy": "path_join",
                    "reverse": False,
                    "delimiter": "_",
                    "fallback": "rule",
                },
                "description": "{path_title} library tests",
            },
            {
                "id": "tools",
                "category": "tools",
                "type": "package",
                "root": "tools",
                "max_depth": 1,
                "tests_dir": "tests",
                "name": {
                    "strategy": "template",
                    "template": "{name_dash}",
                    "fallback": "path",
                },
                "description": "{name_title} tooling tests",
            },
        ],
    }
    (manifest_dir / "manifest.json").write_text(json.dumps(manifest_payload), encoding="utf-8")

    stable_payload = {
        "suites": [
            "alpha",
            {
                "name": "omega",
                "tests": ["tests/test_focus.py"],
            },
        ]
    }
    (manifest_dir / "stable.json").write_text(json.dumps(stable_payload), encoding="utf-8")

    runtime_payload = {"suites": []}
    (manifest_dir / "runtime.json").write_text(json.dumps(runtime_payload), encoding="utf-8")


@pytest.fixture()
def sample_discovery(tmp_path: Path) -> TestSuiteDiscovery:
    repo_root = tmp_path / "repo"
    (repo_root / "libs" / "alpha" / "tests").mkdir(parents=True, exist_ok=True)
    (repo_root / "libs" / "alpha" / "tests" / "test_alpha.py").write_text("assert True\n", encoding="utf-8")

    (repo_root / "tools" / "omega" / "tests").mkdir(parents=True, exist_ok=True)
    (repo_root / "tools" / "omega" / "tests" / "test_focus.py").write_text("assert True\n", encoding="utf-8")

    manifest_dir = tmp_path / "manifests" / "oss"
    _write_manifest(repo_root, manifest_dir)

    manifest = load_manifest(manifest_file=str(manifest_dir / "manifest.json"))
    return TestSuiteDiscovery(str(repo_root), manifest)


def test_tools_category_discovery(sample_discovery: TestSuiteDiscovery) -> None:
    discovery = sample_discovery

    categories = discovery.available_categories()
    assert "tools" in categories

    suites = discovery.get_suites_by_category("tools")
    assert "omega" in suites
    assert suites["omega"].path.endswith("tools/omega/tests")


def test_lib_category_alias(sample_discovery: TestSuiteDiscovery) -> None:
    discovery = sample_discovery

    lib_suites = discovery.get_suites_by_category("lib")
    libs_suites = discovery.get_suites_by_category("libs")
    assert lib_suites
    assert lib_suites.keys() == libs_suites.keys()
