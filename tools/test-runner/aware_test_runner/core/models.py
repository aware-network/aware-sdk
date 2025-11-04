"""Test runner data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TestFailure:
    """Container for individual test failure information."""

    test_name: str
    failure_reason: str
    file_path: str = ""
    line_number: int = 0


@dataclass
class TestResult:
    """Container for test suite results."""

    suite_name: str
    description: str
    path: str
    exit_code: int
    passed: bool
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    failures: List[TestFailure] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class TestSuite:
    """Test suite definition with category information."""

    name: str
    path: str
    category: str
    description: str = ""
    runtime: str = "python"
    command: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    test_selectors: List[str] | None = None
    tags: List[str] = field(default_factory=list)
    setup_commands: List[List[str]] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        """Get the qualified name including category."""
        return f"{self.category}:{self.name}"
