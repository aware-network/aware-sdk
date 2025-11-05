"""Dataclass describing rule specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

Metadata = Mapping[str, object]


@dataclass(frozen=True)
class RuleSpec:
    """Represents a rule document exposed by an environment."""

    id: str
    title: str
    path: Path
    summary: Optional[str] = None
    layer: Optional[str] = None
    version: Optional[str] = None
    metadata: Metadata = field(default_factory=dict)
