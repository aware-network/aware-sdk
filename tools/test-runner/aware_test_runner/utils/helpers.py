"""Helper utility functions."""

from __future__ import annotations

import os
from pathlib import Path


def find_aware_root() -> str:
    """Locate the aware repository root directory."""
    if os.path.exists("/aware"):
        return "/aware"

    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        if parent.name == "aware" and parent.is_dir():
            return str(parent)

    markers = ("aware_sdk", "tools", "libs")
    for parent in current_path.parents:
        if parent.is_dir() and (parent / "pyproject.toml").exists():
            if any((parent / marker).exists() for marker in markers):
                return str(parent)

    for env_var in ("AWARE_ROOT", "AWARE_SDK_ROOT", "WORKSPACE"):
        value = os.environ.get(env_var)
        if value and os.path.exists(value):
            return value

    raise RuntimeError(
        "Could not find aware repository root. "
        "Run this command from within the aware repository "
        "or set the AWARE_ROOT environment variable."
    )
