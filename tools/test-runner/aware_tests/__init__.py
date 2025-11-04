"""Compatibility package that re-exports aware-test-runner under the legacy name."""

from __future__ import annotations

import sys
from importlib import import_module

from aware_test_runner import *  # noqa: F401,F403
from aware_test_runner import __version__  # noqa: F401

_core = import_module("aware_test_runner.core")
_config = import_module("aware_test_runner.config")
_runtime = import_module("aware_test_runner.core.runtime")
_utils = import_module("aware_test_runner.utils")
_test_runner = import_module("aware_test_runner.test_runner")

sys.modules[__name__ + ".core"] = _core
sys.modules[__name__ + ".config"] = _config
sys.modules[__name__ + ".core.runtime"] = _runtime
sys.modules[__name__ + ".utils"] = _utils
sys.modules[__name__ + ".test_runner"] = _test_runner
