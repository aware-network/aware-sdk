"""Local frontmatter helper for environment plan execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import logging
import re

import yaml

logger = logging.getLogger(__name__)

_FRONTMATTER_BOUNDARY = re.compile(r"^---\s*$", re.MULTILINE)


@dataclass(slots=True)
class FrontmatterResult:
    metadata: dict[str, Any]
    body: str


def _parse(text: str) -> FrontmatterResult:
    if not text.startswith("---"):
        return FrontmatterResult(metadata={}, body=text)

    matches = list(_FRONTMATTER_BOUNDARY.finditer(text))
    if len(matches) < 2:
        return FrontmatterResult(metadata={}, body=text)

    start = matches[0].end()
    end = matches[1].start()
    metadata_block = text[start:end]

    metadata: dict[str, Any] = {}
    try:
        loaded = yaml.safe_load(metadata_block) or {}
        if isinstance(loaded, dict):
            metadata = loaded
        else:  # pragma: no cover - defensive logging only
            logger.debug("Unexpected frontmatter payload type: %s", type(loaded))
    except yaml.YAMLError as exc:  # pragma: no cover - defensive logging only
        logger.warning("Failed to parse YAML frontmatter: %s", exc)

    body = text[matches[1].end() :].lstrip("\n")
    return FrontmatterResult(metadata=metadata, body=body)


def load_frontmatter(path: Path) -> FrontmatterResult:
    """Read a markdown document and parse YAML frontmatter if present."""

    return _parse(path.read_text(encoding="utf-8"))


__all__ = ["FrontmatterResult", "load_frontmatter"]
