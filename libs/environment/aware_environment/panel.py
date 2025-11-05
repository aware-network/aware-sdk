"""Panel manifest helpers for UI representations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class PanelManifest:
    """Describes how an object should be rendered in UI (Studio, etc.)."""

    id: str
    description: str = ""
    layout: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)


def validate_panel_manifest(manifest: PanelManifest) -> None:
    """Basic validation hook; extend as schemas evolve."""

    if not manifest.id:
        raise ValueError("PanelManifest requires id")
