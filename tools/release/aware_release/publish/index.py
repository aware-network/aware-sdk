"""Release index helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..schemas.release import BundleManifest, ReleaseIndex, ReleaseIndexEntry


def load_release_index(path: Path) -> ReleaseIndex:
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return ReleaseIndex.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid release index at {path}: {exc}") from exc
    return ReleaseIndex(entries=[])


def update_release_index(
    index: ReleaseIndex,
    manifest: BundleManifest,
    url: Optional[str],
    notes: Optional[str],
    signature_path: Optional[Path],
) -> ReleaseIndex:
    checksum = manifest.checksum
    entry = ReleaseIndexEntry(
        channel=manifest.channel,
        version=manifest.version,
        url=url or "",
        checksum=checksum,
        released_at=datetime.now(timezone.utc),
        notes=notes,
    )
    index.entries = [
        existing
        for existing in index.entries
        if not (existing.channel == entry.channel and existing.version == entry.version)
    ]
    index.entries.append(entry)
    index.entries.sort(key=lambda item: (item.channel, item.version, item.released_at))
    return index
