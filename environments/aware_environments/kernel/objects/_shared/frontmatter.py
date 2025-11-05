"""Minimal YAML frontmatter parser for kernel runtime documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple
import logging

import yaml

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FrontmatterResult:
    metadata: dict[str, Any]
    body: str


def _looks_like_markdown_frontmatter(block: str) -> bool:
    for raw_line in block.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return True
        if stripped.startswith("```"):
            return True
        if stripped.startswith(">"):
            return True
        if stripped.startswith("- **"):
            return True
    return False


def _split_frontmatter_and_body(text: str) -> Optional[Tuple[str, str]]:
    if not text.startswith("---"):
        return None

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            frontmatter = "".join(lines[1:index])
            if _looks_like_markdown_frontmatter(frontmatter):
                return None
            body = "".join(lines[index + 1 :])
            return frontmatter, body

    return None


def _parse(text: str, *, source: Optional[str] = None) -> FrontmatterResult:
    split_result = _split_frontmatter_and_body(text)
    if split_result is None:
        return FrontmatterResult(metadata={}, body=text)

    metadata_block, body_block = split_result

    metadata: dict[str, Any] = {}
    try:
        loaded = yaml.safe_load(metadata_block) or {}
        if isinstance(loaded, dict):
            metadata = loaded
        else:  # pragma: no cover - unexpected type warnings only
            logger.debug("Unexpected frontmatter payload type: %s", type(loaded))
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        source_desc = f" ({source})" if source else ""
        logger.warning("Failed to parse YAML frontmatter%s: %s", source_desc, exc)
        metadata = {}

    body = body_block.lstrip("\n")
    return FrontmatterResult(metadata=metadata, body=body)


def load_frontmatter(path: Path) -> FrontmatterResult:
    return _parse(path.read_text(encoding="utf-8"), source=str(path))


__all__ = ["FrontmatterResult", "load_frontmatter"]
