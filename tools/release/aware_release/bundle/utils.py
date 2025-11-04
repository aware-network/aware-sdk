"""Shared helpers used by bundle tooling."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional


def compute_sha256(path: Path) -> str:
    """Return the SHA-256 checksum for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(payload: Any, path: Path) -> None:
    """Write JSON payload to disk with canonical formatting."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str, *, newline: Optional[str] = None) -> None:
    """Write text to file ensuring parent directories exist."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline=newline)
