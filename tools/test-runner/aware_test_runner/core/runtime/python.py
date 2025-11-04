"""Runtime executor for pytest-based suites."""

from __future__ import annotations

import os
import sys
from typing import List, Optional

import pytest

from ..collector import TestResultCollector
from ..models import TestResult, TestSuite
from .base import RuntimeExecutor


class PythonRuntimeExecutor(RuntimeExecutor):
    """Execute pytest-based suites."""

    def run(
        self,
        suite: TestSuite,
        *,
        verbose: bool,
        fail_fast: bool,
        xvs: Optional[List[str]],
        no_warnings: bool,
        update_golden: bool,
    ) -> TestResult:
        result_collector = TestResultCollector()
        original_cwd = os.getcwd()
        suite_parent = os.path.dirname(suite.path)
        env_overrides = suite.env or {}
        previous_env: dict[str, Optional[str]] = {}

        try:
            if suite_parent:
                os.chdir(suite_parent)

            for key, value in env_overrides.items():
                previous_env[key] = os.environ.get(key)
                os.environ[key] = value

            result_collector.reset()
            pytest_args: List[str] = []

            relative_test_path = os.path.basename(suite.path)

            if no_warnings:
                pytest_args.extend(["-p", "no:warnings"])
                os.environ["PYTHONWARNINGS"] = "ignore"

            if update_golden:
                pytest_args.append("--update-golden")

            if fail_fast:
                pytest_args.append("-x")

            pytest_args.extend(["--tb=no", "--no-header", "--disable-warnings", "-rN"])

            if not verbose:
                pytest_args.append("-q")
            else:
                pytest_args.extend(["-v", "--tb=short", "--log-cli-level=INFO"])
                if "--tb=no" in pytest_args:
                    pytest_args.remove("--tb=no")

            if xvs:
                pytest_args.extend(xvs)

            selectors = suite.test_selectors or []
            if selectors:
                pytest_args.extend([f"{relative_test_path}/{selector}" for selector in selectors])
            else:
                pytest_args.append(relative_test_path)

            exit_code = pytest.main(pytest_args + ["-p", "no:cacheprovider"], plugins=[result_collector])
            total_tests, passed_tests, failed_tests, skipped_tests, failures = result_collector.get_results()
            duration = result_collector.get_duration()

            result = TestResult(
                suite_name=suite.name,
                description=suite.description,
                path=suite.path,
                exit_code=exit_code,
                passed=(exit_code == 0),
                total_tests=total_tests,
                passed_tests=passed_tests,
                failed_tests=failed_tests,
                skipped_tests=skipped_tests,
                failures=failures,
                duration=duration,
            )

            if "tests" in sys.modules:
                del sys.modules["tests"]
            if "tests.conftest" in sys.modules:
                del sys.modules["tests.conftest"]

            return result
        finally:
            os.chdir(original_cwd)
            for key, previous in previous_env.items():
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous
