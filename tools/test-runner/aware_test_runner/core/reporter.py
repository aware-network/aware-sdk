"""Test result reporting functionality."""

from __future__ import annotations

from typing import List

from .models import TestResult


class TestReporter:
    """Handles test result reporting and output formatting."""

    def __init__(self, aware_root: str):
        self.aware_root = aware_root

    def print_available_suites(self, discovery) -> None:  # pragma: no cover - side effects only
        """Print all available test suites organized by category."""
        print("Available test suites:")
        print(f"Using Aware repository at: {self.aware_root}")
        print()

        for category in discovery.available_categories():
            suites = discovery.get_suites_by_category(category)
            if suites:
                print(f"📁 {category.upper()}:")
                for name, suite in suites.items():
                    print(f"   {name}: {suite.description} ({suite.path})")
                print()

        print("Usage examples:")
        print("  --suites core evolution        # Run specific suites")
        print("  --suites lib                   # Run all lib suites")
        print("  --stable                       # Run the curated stable suite list")
        print("  --suites grammar domains       # Run all grammar and domain suites")
        print("  --suites lib:core domains:meta # Run specific suites from categories")
        print("  --suites all                   # Run all suites")

    def print_test_summary(self, results: List[TestResult]) -> None:  # pragma: no cover - side effects only
        """Print a comprehensive summary of all test results."""
        print("\n" + "=" * 80)
        print("TEST SUITE SUMMARY")
        print("=" * 80)

        passed_suites = [r for r in results if r.passed]
        failed_suites = [r for r in results if not r.passed]

        total_tests = sum(r.total_tests for r in results)
        total_passed = sum(r.passed_tests for r in results)
        total_failed = sum(r.failed_tests for r in results)
        total_skipped = sum(r.skipped_tests for r in results)
        total_duration = sum(r.duration for r in results)

        print(f"Total test suites: {len(results)}")
        print(f"Suite results: {len(passed_suites)} passed, {len(failed_suites)} failed")
        print(
            f"Individual tests: {total_tests} total, {total_passed} passed, {total_failed} failed, {total_skipped} skipped"
        )
        print(f"Total duration: {total_duration:.2f}s")
        print()

        if passed_suites:
            print("✅ PASSED SUITES:")
            for result in passed_suites:
                test_summary = f"{result.passed_tests} passed"
                if result.skipped_tests > 0:
                    test_summary += f", {result.skipped_tests} skipped"
                print(f"   {result.suite_name} - {result.description} ({test_summary})")
            print()

        if failed_suites:
            print("❌ FAILED SUITES:")
            for result in failed_suites:
                test_summary = f"{result.failed_tests} failed"
                if result.passed_tests > 0:
                    test_summary += f", {result.passed_tests} passed"
                if result.skipped_tests > 0:
                    test_summary += f", {result.skipped_tests} skipped"
                print(f"   {result.suite_name} - {result.description} ({test_summary})")
            print()

            print("🔍 DETAILED FAILURES:")
            print("-" * 60)
            for result in failed_suites:
                if result.failures:
                    print(f"\n📋 {result.suite_name} failures:")
                    for index, failure in enumerate(result.failures, 1):
                        print(f"   {index}. {failure.test_name}")
                        if failure.failure_reason:
                            reason = failure.failure_reason
                            if len(reason) > 100:
                                reason = reason[:97] + "..."
                            print(f"      💥 {reason}")
                else:
                    print(f"\n📋 {result.suite_name}: Suite failed but no specific test failures captured")
            print()

        print("DETAILED RESULTS:")
        print("-" * 40)
        for result in results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            test_info = f"({result.total_tests} tests)" if result.total_tests > 0 else ""
            duration_info = f"{result.duration:.1f}s" if result.duration > 0 else ""
            print(f"{status} {result.suite_name:<20} {result.description} {test_info} {duration_info}")

        print("\n" + "=" * 80)
        if failed_suites:
            print(
                f"OVERALL RESULT: ❌ FAILED ({len(failed_suites)} suite(s) failed, {total_failed} individual test(s) failed)"
            )
        else:
            print(f"OVERALL RESULT: ✅ ALL TESTS PASSED ({total_tests} tests across {len(results)} suites)")
        print("=" * 80)
