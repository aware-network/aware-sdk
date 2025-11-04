"""Test result collection functionality."""

from __future__ import annotations

import time
from typing import List, Tuple

from .models import TestFailure


class TestResultCollector:
    """Custom pytest plugin to collect detailed test results."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset collector state for a new test run."""
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        self.failures: List[TestFailure] = []
        self.start_time: float | None = None
        self.end_time: float | None = None

    def pytest_sessionstart(self, session) -> None:  # pragma: no cover - pytest hook
        """Called when pytest session starts."""
        del session
        self.start_time = time.time()

    def pytest_sessionfinish(self, session) -> None:  # pragma: no cover - pytest hook
        """Called when pytest session finishes."""
        del session
        self.end_time = time.time()

    def pytest_runtest_logreport(self, report) -> None:  # pragma: no cover - pytest hook
        """Called for each test result (setup, call, teardown)."""
        if report.when != "call":
            return

        self.total_tests += 1

        if report.outcome == "passed":
            self.passed_tests += 1
            return

        if report.outcome == "failed":
            self.failed_tests += 1
            test_name = report.nodeid.split("::")[-1] if "::" in report.nodeid else report.nodeid
            failure_reason = "Test failed"
            if hasattr(report, "longrepr") and report.longrepr:
                try:
                    if hasattr(report.longrepr, "reprcrash") and report.longrepr.reprcrash:
                        failure_reason = str(report.longrepr.reprcrash.message)
                    elif hasattr(report.longrepr, "reprtraceback"):
                        lines = str(report.longrepr).split("\n")
                        for line in reversed(lines):
                            line = line.strip()
                            if line and not line.startswith("=") and not line.startswith("_"):
                                failure_reason = line
                                break
                    else:
                        failure_reason = str(report.longrepr)[:200]
                except Exception:  # pragma: no cover - defensive
                    failure_reason = "Test failed"

            failure = TestFailure(test_name=test_name, failure_reason=failure_reason, file_path=report.nodeid)
            self.failures.append(failure)
            return

        if report.outcome == "skipped":
            self.skipped_tests += 1

    def get_duration(self) -> float:
        """Get test duration in seconds."""
        if self.start_time is not None and self.end_time is not None:
            return self.end_time - self.start_time
        return 0.0

    def get_results(self) -> Tuple[int, int, int, int, List[TestFailure]]:
        """Get collected results as tuple."""
        return (self.total_tests, self.passed_tests, self.failed_tests, self.skipped_tests, self.failures)
