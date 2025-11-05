"""Smoke tests for the aware-test-runner package."""

import json
from pathlib import Path

import pytest

from aware_test_runner import __version__
from aware_test_runner.config import load_manifest
from aware_test_runner.test_runner import AwareTestRunner


@pytest.fixture()
def sample_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "libs" / "alpha" / "tests").mkdir(parents=True, exist_ok=True)
    (repo_root / "libs" / "alpha" / "tests" / "test_alpha.py").write_text("assert True\n", encoding="utf-8")

    manifest_dir = tmp_path / "manifests" / "oss"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    manifest_payload = {
        "id": "oss-test",
        "discovery": [
            {
                "id": "libraries",
                "category": "lib",
                "type": "package",
                "root": "libs",
                "max_depth": 1,
                "tests_dir": "tests",
                "name": {"strategy": "path_join", "delimiter": "_"},
            }
        ],
    }
    (manifest_dir / "manifest.json").write_text(json.dumps(manifest_payload), encoding="utf-8")
    (manifest_dir / "stable.json").write_text(json.dumps({"suites": ["alpha"]}), encoding="utf-8")
    (manifest_dir / "runtime.json").write_text(json.dumps({"suites": []}), encoding="utf-8")

    monkeypatch.setenv("AWARE_ROOT", str(repo_root))
    return manifest_dir / "manifest.json"


def test_version_not_placeholder() -> None:
    assert __version__ != "0.0.0"


def test_runner_resolves_root(sample_manifest: Path) -> None:
    manifest = load_manifest(manifest_file=str(sample_manifest))
    runner = AwareTestRunner(manifest=manifest)
    assert Path(runner.aware_root).exists()
