"""Test runner orchestration for aware-test-runner."""

from __future__ import annotations

import argparse
import sys

from .config import ManifestData, load_manifest
from .core import TestReporter, TestSuiteDiscovery, TestExecutor, expand_suite_selectors
from .utils import find_aware_root


class AwareTestRunner:
    """Main test runner orchestrator."""

    def __init__(self, manifest: ManifestData | None = None):
        self.aware_root = find_aware_root()
        self.manifest = manifest or load_manifest()
        self.discovery = TestSuiteDiscovery(self.aware_root, self.manifest)
        self.executor = TestExecutor(self.aware_root)
        self.reporter = TestReporter(self.aware_root)

    def list_suites(self) -> None:
        """List all available test suites."""
        self.reporter.print_available_suites(self.discovery)

    def run_tests(
        self,
        suite_selectors: list[str] | None,
        verbose: bool = False,
        fail_fast: bool = False,
        xvs: list[str] | None = None,
        no_warnings: bool = True,
        update_golden: bool = False,
        stable_only: bool = False,
    ) -> int:
        """Run the specified test suites."""
        suite_names = expand_suite_selectors(suite_selectors or [], self.discovery)

        if not suite_names:
            print("No valid test suites found. Use --list to see available options.")
            return 1

        available_suites = self.discovery.discover_all_suites()
        if stable_only:
            stable_overrides = self.discovery.get_suites_by_category("stable")
            for name, suite in stable_overrides.items():
                if name in available_suites:
                    available_suites[name] = suite

        invalid_suites = [name for name in suite_names if name not in available_suites]
        if invalid_suites:
            print(f"Error: Unknown test suites: {', '.join(invalid_suites)}")
            print("Use --list to see available test suites")
            return 1

        suites_to_run = [available_suites[name] for name in suite_names]

        results = self.executor.run_test_suites(
            suites=suites_to_run,
            verbose=verbose,
            fail_fast=fail_fast,
            xvs=xvs or [],
            no_warnings=no_warnings,
            update_golden=update_golden,
        )

        self.reporter.print_test_summary(results)

        failure_count = len([result for result in results if not result.passed])
        return 1 if failure_count > 0 else 0


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Run Aware test suites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  aware-tests --suites core evolution        # Run specific suites
  aware-tests --suites grammar domains       # Run all grammar and domain suites
  aware-tests --suites lib:core domains:meta # Run specific suites from categories
  aware-tests --stable                       # Run the curated stable suite list
  aware-tests --suites all                   # Run all suites
        """,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the test runner."""
    parser = _build_parser()

    parser.add_argument(
        "--suites",
        nargs="+",
        default=None,
        help="Test suites to run. Can be suite names, category names, or category:suite format. Use 'all' for all suites.",
    )

    parser.add_argument(
        "--manifest",
        help="Manifest identifier to load (defaults to AWARE_TEST_RUNNER_MANIFEST or 'oss').",
    )

    parser.add_argument(
        "--manifest-file",
        help="Path to a manifest file or directory containing stable.json/runtime.json definitions.",
    )

    parser.add_argument(
        "--stable",
        action="store_true",
        help="Run only the curated stable suite list defined by the active manifest.",
    )

    parser.add_argument("--list", action="store_true", help="List available test suites and exit")

    parser.add_argument("-v", "--verbose", action="store_true", help="Run tests in verbose mode")

    parser.add_argument("-f", "--fail-fast", action="store_true", help="Stop after first test failure")

    parser.add_argument("--xvs", nargs="+", default=None, help="Extra arguments to pass to pytest")

    parser.add_argument("--no-warnings", action="store_true", help="Suppress warnings during test execution")

    parser.add_argument("--update-golden", action="store_true", help="Update golden test files")

    args = parser.parse_args(argv)

    if args.manifest and args.manifest_file:
        parser.error("--manifest and --manifest-file cannot be used together")

    if args.stable and args.suites:
        parser.error("--stable cannot be combined with --suites")

    manifest = load_manifest(manifest_id=args.manifest, manifest_file=args.manifest_file)
    runner = AwareTestRunner(manifest=manifest)

    if args.list:
        runner.list_suites()
        return 0

    suite_selectors = ["stable"] if args.stable else args.suites

    return runner.run_tests(
        suite_selectors=suite_selectors,
        verbose=args.verbose,
        fail_fast=args.fail_fast,
        xvs=args.xvs,
        no_warnings=args.no_warnings,
        update_golden=args.update_golden,
        stable_only=args.stable,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
