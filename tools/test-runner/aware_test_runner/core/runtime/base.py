"""Base interface for runtime-specific test executors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import TestResult, TestSuite


class RuntimeExecutor(ABC):
    """Base interface for runtime-specific test executors."""

    def __init__(self, aware_root: str):
        self.aware_root = aware_root

    @abstractmethod
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
        """Execute the provided test suite and return a test result."""
        raise NotImplementedError
