from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class SessionMeta:
    description: Optional[str] = None
    tags: Optional[list[str]] = None


class MetadataStore:
    def __init__(self, base: Optional[Path] = None) -> None:
        self.base = base or (Path.home() / ".aware" / "terminal")
        self.base.mkdir(parents=True, exist_ok=True)
        self.path = self.base / "sessions.json"
        self._data: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except Exception:
                self._data = {}

    def get(self, name: str) -> SessionMeta:
        raw = self._data.get(name) or {}
        return SessionMeta(description=raw.get("description"), tags=raw.get("tags"))

    def set(self, name: str, meta: SessionMeta) -> None:
        self._data[name] = {
            "description": meta.description,
            "tags": meta.tags or [],
        }
        self.path.write_text(json.dumps(self._data, indent=2))

