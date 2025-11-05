from __future__ import annotations

import os
import tempfile
from pathlib import Path


def aware_root() -> Path:
    custom = os.environ.get("AWARE_HOME")
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".aware"


def thread_dir(thread: str) -> Path:
    return aware_root() / "threads" / thread


def manifest_path(thread: str) -> Path:
    return thread_dir(thread) / "terminal" / "manifest.json"


def default_socket_path(thread: str) -> Path:
    runtime = os.environ.get("AWARE_RUNTIME_DIR") or os.environ.get("XDG_RUNTIME_DIR")
    base = Path(runtime) if runtime else Path(tempfile.gettempdir())
    return base / "aware-terminal" / f"{thread}.sock"
