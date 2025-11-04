"""Utilities for extracting dependencies from wheel metadata."""

from __future__ import annotations

import zipfile
from email.parser import Parser
from pathlib import Path
from typing import Iterable, List, Set


def collect_dependencies(wheels: Iterable[Path]) -> List[str]:
    """Collect Requires-Dist entries from wheel METADATA files."""

    requirements: Set[str] = set()
    for wheel in wheels:
        requirements.update(_read_wheel_requirements(wheel))
    return sorted(requirements)


def _read_wheel_requirements(path: Path) -> List[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_name = next(
                (name for name in archive.namelist() if name.endswith(".dist-info/METADATA")),
                None,
            )
            if metadata_name is None:
                return []
            with archive.open(metadata_name) as handle:
                metadata_text = handle.read().decode("utf-8", errors="replace")
    except (FileNotFoundError, zipfile.BadZipFile):
        return []

    message = Parser().parsestr(metadata_text)
    return [
        entry.strip()
        for entry in message.get_all("Requires-Dist", [])
        if entry and entry.strip()
    ]
