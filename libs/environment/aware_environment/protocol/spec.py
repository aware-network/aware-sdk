"""Dataclasses describing protocol specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Tuple

Metadata = Mapping[str, object]


@dataclass(frozen=True)
class ProtocolTarget:
    """Binding target for a protocol (object and optional functions)."""

    object_type: str
    functions: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ProtocolSpec:
    """Represents a decision-guidance protocol exposed by an environment."""

    id: str
    slug: str
    title: str
    path: Path
    summary: Optional[str] = None
    version: Optional[str] = None
    targets: Tuple[ProtocolTarget, ...] = ()
    metadata: Metadata = field(default_factory=dict)
