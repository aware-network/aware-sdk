"""Dataclass describing role specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Tuple

Metadata = Mapping[str, object]


@dataclass(frozen=True)
class RoleSpec:
    """Represents an agent role and the policies it references."""

    slug: str
    title: str
    description: str
    policy_ids: Tuple[str, ...]
    protocol_ids: Tuple[str, ...] = ()
    metadata: Metadata = field(default_factory=dict)
