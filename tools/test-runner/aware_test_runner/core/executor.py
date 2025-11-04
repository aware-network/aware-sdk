"""Test execution functionality."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import List, Optional

from .models import TestFailure, TestResult, TestSuite
from .runtime.registry import RuntimeExecutorRegistry


class SetupCommandError(RuntimeError):
    """Raised when a suite setup command fails."""


class TestExecutor:
    """Handles test execution logic across runtimes."""

    def __init__(self, aware_root: str, setup_kernel: bool = False):
        self.aware_root = aware_root
        self._setup_environment()
        if setup_kernel:
            self._setup_kernel()
        self.registry = RuntimeExecutorRegistry(aware_root)

    def _setup_environment(self) -> None:
        """Set up environment for test execution."""
        env = os.environ.copy()

        if "PYTHONPATH" not in env:
            env["PYTHONPATH"] = self.aware_root
        else:
            env["PYTHONPATH"] = f"{env['PYTHONPATH']}:{self.aware_root}"

        if self.aware_root not in sys.path:
            sys.path.insert(0, self.aware_root)

    def _setup_kernel(self) -> None:
        """Setup Aware kernel environment for Python tests."""
        print("Setting up Aware kernel environment...")
        try:
            from aware_core.bootstrap import ensure_ready

            ensure_ready()
            print("Aware kernel environment setup successfully.")
        except ImportError as exc:  # pragma: no cover - defensive
            print(f"Warning: Could not import ensure_ready from aware_core.bootstrap: {exc}")
            print("Tests will run without kernel environment setup.")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Warning: Failed to setup Aware kernel environment: {exc}")
            print("Tests will run without kernel environment setup.")

    def run_test_suite(
        self,
        suite: TestSuite,
        verbose: bool = False,
        fail_fast: bool = False,
        xvs: Optional[List[str]] = None,
        no_warnings: bool = True,
        update_golden: bool = False,
    ) -> TestResult:
        """Run a single test suite using the registered runtime executor."""
        executor = self.registry.get_executor(suite.runtime)
        if executor is None:
            message = f"Unsupported runtime '{suite.runtime}' for suite {suite.qualified_name}"
            print(f"❌ {message}")
            return TestResult(
                suite_name=suite.name,
                description=suite.description,
                path=suite.path,
                exit_code=1,
                passed=False,
                failures=[TestFailure(test_name=suite.name, failure_reason=message)],
            )

        try:
            setup_total = len(suite.setup_commands)
            for setup_index, setup_cmd in enumerate(suite.setup_commands, 1):
                self._run_setup_command(setup_cmd, suite, setup_index, setup_total)

            return executor.run(
                suite,
                verbose=verbose,
                fail_fast=fail_fast,
                xvs=xvs,
                no_warnings=no_warnings,
                update_golden=update_golden,
            )
        except SetupCommandError as exc:
            return TestResult(
                suite_name=suite.name,
                description=suite.description,
                path=suite.path,
                exit_code=1,
                passed=False,
                failures=[TestFailure(test_name=suite.name, failure_reason=str(exc))],
            )
        except RuntimeError as exc:
            print(f"❌ ERROR running {suite.category}:{suite.name}: {exc}")
            return TestResult(
                suite_name=suite.name,
                description=suite.description,
                path=suite.path,
                exit_code=1,
                passed=False,
                failures=[TestFailure(test_name=suite.name, failure_reason=str(exc))],
            )
        except Exception as exc:  # pragma: no cover - defensive
            print(f"❌ Unexpected error running {suite.category}:{suite.name}: {exc}")
            return TestResult(
                suite_name=suite.name,
                description=suite.description,
                path=suite.path,
                exit_code=1,
                passed=False,
                failures=[TestFailure(test_name=suite.name, failure_reason=str(exc))],
            )

    def _run_setup_command(self, setup_cmd: List[str], suite: TestSuite, index: int, total: int) -> None:
        """Run an individual setup command with streaming output and timestamps."""
        if not setup_cmd:
            return

        timestamp = self._timestamp()
        command_display = " ".join(shlex.quote(part) for part in setup_cmd)
        print(f"[{timestamp}] ▶ Setup ({index}/{total}): {command_display} (cwd={suite.path})")
        env = os.environ.copy()
        start_time = time.perf_counter()

        process = subprocess.Popen(
            setup_cmd,
            cwd=suite.path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        output_lines: List[str] = []
        assert process.stdout is not None
        try:
            for line in process.stdout:
                output_lines.append(line)
                print(line, end="")
        except Exception as exc:  # pragma: no cover - defensive
            output_lines.append(str(exc))
            print(f"\n[{self._timestamp()}] ⚠️  Error reading setup output: {exc}")
        finally:
            process.stdout.close()

        process.wait()
        duration = time.perf_counter() - start_time

        if process.returncode != 0:
            merged_output = "".join(output_lines).strip()
            failure_message = merged_output or f"Setup command '{command_display}' failed"
            print(
                f"[{self._timestamp()}] ❌ Setup ({index}/{total}) failed for {suite.qualified_name}: {failure_message}"
            )
            raise SetupCommandError(failure_message)

        print(f"[{self._timestamp()}] ✓ Setup ({index}/{total}) completed in {duration:.1f}s for {suite.qualified_name}")

    @staticmethod
    def _timestamp() -> str:
        """Return a UTC timestamp suitable for logs."""
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def run_test_suites(
        self,
        suites: List[TestSuite],
        verbose: bool = False,
        fail_fast: bool = False,
        xvs: Optional[List[str]] = None,
        no_warnings: bool = True,
        update_golden: bool = False,
    ) -> List[TestResult]:
        """Run multiple test suites sequentially."""
        if not suites:
            return []

        print(f"\n🚀 Starting test run for {len(suites)} suite(s): {', '.join([s.name for s in suites])}")
        print("=" * 80)

        results: List[TestResult] = []
        for index, suite in enumerate(suites, 1):
            print(f"\n[{index}/{len(suites)}] Running {suite.category}:{suite.name} tests ({suite.description})")
            print(f"Test path: {suite.path}")
            print(f"Runtime: {suite.runtime}")
            print("-" * 60)

            result = self.run_test_suite(
                suite=suite,
                verbose=verbose,
                fail_fast=fail_fast,
                xvs=xvs,
                no_warnings=no_warnings,
                update_golden=update_golden,
            )
            results.append(result)

            status = "✅ PASSED" if result.passed else "❌ FAILED"
            duration_info = f", {result.duration:.1f}s" if result.duration else ""
            print(f"\n{status} - {suite.category}:{suite.name}{duration_info}")

            if result.failures:
                failure_count = len(result.failures)
                preview = min(failure_count, 3)
                print(f"   Failures: {failure_count}")
                for failure in result.failures[:preview]:
                    print(f"   • {failure.test_name}")
                if failure_count > preview:
                    print("   (additional failures omitted)")

            if fail_fast and not result.passed:
                print(f"\n⚠️  Stopping due to --fail-fast after {suite.category}:{suite.name} failure")
                break

        return results
