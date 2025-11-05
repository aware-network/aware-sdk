"\"\"\"Environment helpers for terminal providers.\"\"\""

from __future__ import annotations

import os
from pathlib import Path


def get_home_directory(env_var: str, default_subdir: str) -> Path:
    base = os.environ.get(env_var)
    if base:
        return Path(base).expanduser()
    return Path.home() / default_subdir


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
