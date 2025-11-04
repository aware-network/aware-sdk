"""Smoke tests for the aware-test-runner package."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from aware_test_runner import __version__
from aware_test_runner.test_runner import AwareTestRunner


def test_version_not_placeholder() -> None:
    assert __version__ != "0.0.0"


def test_runner_resolves_root() -> None:
    runner = AwareTestRunner()
    assert Path(runner.aware_root).name == "aware"
