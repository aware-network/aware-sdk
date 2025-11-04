"""aware-test-runner package."""

from .core import (
    TestFailure,
    TestResult,
    TestSuite,
    TestSuiteDiscovery,
    TestResultCollector,
    TestExecutor,
    TestReporter,
    expand_suite_selectors,
)
from .test_runner import AwareTestRunner, main
from .utils import find_aware_root

__all__ = [
    "__version__",
    "AwareTestRunner",
    "TestFailure",
    "TestResult",
    "TestSuite",
    "TestSuiteDiscovery",
    "TestResultCollector",
    "TestExecutor",
    "TestReporter",
    "expand_suite_selectors",
    "find_aware_root",
    "main",
]

__version__ = "0.1.4"
