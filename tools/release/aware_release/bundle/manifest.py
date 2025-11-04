"""Manifest helpers for bundle assembly."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..schemas.release import BundleManifest


def load_manifest(path: Path) -> BundleManifest:
    """Load a manifest from JSON."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return BundleManifest.model_validate(payload)


def dump_manifest(manifest: BundleManifest, path: Path) -> None:
    """Write a manifest to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")


def merge_manifest(manifest: BundleManifest, overrides: Mapping[str, Any]) -> BundleManifest:
    """Return a new manifest with overrides applied."""

    payload = manifest.model_dump()
    payload.update(overrides)
    return BundleManifest.model_validate(payload)
