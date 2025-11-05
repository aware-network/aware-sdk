from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import Manifest, SessionRecord, _utc_now


class ManifestStore:
    """Read/write helper for thread terminal manifests."""

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Manifest:
        if not self.manifest_path.exists():
            raise FileNotFoundError(self.manifest_path)
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return Manifest.model_validate(data)

    def load_or_create(self, thread: str, socket_path: Path) -> Manifest:
        if self.manifest_path.exists():
            return self.load()
        manifest = Manifest(thread=thread, socket_path=socket_path, sessions=[], updated_at=_utc_now())
        self.write(manifest)
        return manifest

    def write(self, manifest: Manifest) -> None:
        payload = manifest.as_dict()
        self.manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def update_session(self, manifest: Manifest, record: SessionRecord) -> Manifest:
        sessions = [sess for sess in manifest.sessions if sess.session_id != record.session_id]
        sessions.append(record)
        updated = manifest.copy(update={"sessions": sessions, "updated_at": _utc_now()})
        self.write(updated)
        return updated

    def remove_session(self, manifest: Optional[Manifest], session_id: str) -> Manifest:
        if manifest is None:
            manifest = self.load()
        sessions = [sess for sess in manifest.sessions if sess.session_id != session_id]
        updated = manifest.copy(update={"sessions": sessions, "updated_at": _utc_now()})
        self.write(updated)
        return updated
