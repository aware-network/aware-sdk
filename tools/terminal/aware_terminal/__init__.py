"""aware-terminal package entry."""

from __future__ import annotations

import sys

__all__ = ["cli"]

# Expose `aware_terminal` as an importable alias when the package is loaded via `tools.terminal.aware_terminal`.
sys.modules.setdefault("aware_terminal", sys.modules[__name__])
