"""Studio integration helpers."""

from __future__ import annotations

from pathlib import Path

from ..schemas.release import BundleManifest


def apply_bundle(bundle_path: Path, manifest: BundleManifest) -> None:
    """Activate a bundle inside Studio resources."""

    raise NotImplementedError("apply_bundle pending implementation.")
