"""Runtime executor for Flutter test suites."""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import List, Optional

from ..models import TestFailure, TestResult, TestSuite
from .base import RuntimeExecutor

DEFAULT_COMMAND: List[str] = ["flutter", "test", "--machine"]
MAX_FAILURE_SNIPPET = 2000


def _parse_machine_stream(stream) -> dict:
    passed = failed = skipped = 0
    failure_snippets: List[str] = []

    for raw_line in stream:
        line = raw_line.strip()
        if not line or line.startswith("["):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type")
        if event_type == "testDone":
            if event.get("hidden"):
                continue
            result = event.get("result")
            if result == "success":
                passed += 1
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1
        elif event_type == "print":
            message = event.get("message")
            if message:
                failure_snippets.append(message)
        elif event_type == "error":
            error = event.get("error")
            if error:
                failure_snippets.append(error)

    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "snippets": failure_snippets,
    }


class FlutterRuntimeExecutor(RuntimeExecutor):
    """Execute Flutter test suites via the flutter tool."""

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
        command = list(suite.command or DEFAULT_COMMAND)
        if "--machine" not in command:
            command.append("--machine")

        selectors = suite.test_selectors or []
        if selectors:
            command.extend(selectors)
        if xvs:
            command.extend(xvs)

        env = os.environ.copy()
        for key, value in (suite.env or {}).items():
            env[key] = value

        cwd = suite.path
        start = time.perf_counter()

        try:
            proc = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Flutter executable not found. Ensure Flutter is installed and 'flutter' is on PATH."
            ) from exc

        summary = _parse_machine_stream(proc.stdout or [])
        stderr = proc.stderr.read() if proc.stderr else ""
        proc.wait()
        duration = time.perf_counter() - start

        passed = summary["failed"] == 0 and proc.returncode == 0
        failures: List[TestFailure] = []
        if not passed:
            snippet = "\n".join(summary["snippets"])
            if not snippet:
                snippet = stderr.strip()
            if snippet and len(snippet) > MAX_FAILURE_SNIPPET:
                snippet = snippet[-MAX_FAILURE_SNIPPET:]
            failures.append(
                TestFailure(
                    test_name=suite.name,
                    failure_reason=snippet or "Flutter test suite failed with no output.",
                    file_path=cwd,
                )
            )

        return TestResult(
            suite_name=suite.name,
            description=suite.description,
            path=suite.path,
            exit_code=proc.returncode or 0,
            passed=passed,
            total_tests=summary["passed"] + summary["failed"] + summary["skipped"],
            passed_tests=summary["passed"],
            failed_tests=summary["failed"],
            skipped_tests=summary["skipped"],
            failures=failures,
            duration=duration,
        )
