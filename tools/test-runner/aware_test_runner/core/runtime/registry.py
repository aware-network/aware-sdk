"""Runtime executor registry."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from .base import RuntimeExecutor
from .flutter import FlutterRuntimeExecutor
from .python import PythonRuntimeExecutor


class RuntimeExecutorRegistry:
    """Registry mapping runtime identifiers to concrete executors."""

    def __init__(self, aware_root: str):
        self.aware_root = aware_root
        self._executors: Dict[str, RuntimeExecutor] = {}
        self.register("python", PythonRuntimeExecutor(aware_root))
        self.register("flutter", FlutterRuntimeExecutor(aware_root))

    def register(self, runtime: str, executor: RuntimeExecutor) -> None:
        """Register or override the executor for a runtime."""
        self._executors[runtime] = executor

    def get_executor(self, runtime: str) -> Optional[RuntimeExecutor]:
        """Return the executor for the requested runtime, if registered."""
        return self._executors.get(runtime)

    def supported_runtimes(self) -> Iterable[str]:
        """Return the registered runtime identifiers."""
        return self._executors.keys()
