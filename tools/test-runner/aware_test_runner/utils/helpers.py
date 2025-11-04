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

    for env_var in ("AWARE_ROOT", "WORKSPACE"):
        value = os.environ.get(env_var)
        if value and os.path.exists(value):
            return value

    raise RuntimeError(
        "Could not find aware repository root. "
        "Run this command from within the aware repository "
        "or set the AWARE_ROOT environment variable."
    )
