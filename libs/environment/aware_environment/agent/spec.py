"""Dataclass describing agent specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Tuple

Metadata = Mapping[str, object]


@dataclass(frozen=True)
class AgentSpec:
    """Represents an agent exposed by an environment."""

    slug: str
    title: str
    role_slugs: Tuple[str, ...]
    description: str = ""
    metadata: Metadata = field(default_factory=dict)
