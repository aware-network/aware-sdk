"""Data models used during release publishing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..schemas.release import BundleManifest


@dataclass(slots=True)
class UploadResult:
    adapter: str
    status: str
    url: Optional[str] = None
    details: Dict[str, object] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)


@dataclass(slots=True)
class PublishResult:
    manifest_path: Path
    archive_path: Path
    checksum_match: bool
    index_path: Optional[Path]
    index_updated: bool
    signature_path: Optional[Path]
    upload: UploadResult
    logs: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class PublishContext:
    manifest_path: Path
    archive_path: Path
    manifest: BundleManifest
    url: Optional[str]
    notes: Optional[str]
    dry_run: bool
    adapter_name: str
    adapter_options: Dict[str, object]
    releases_index_path: Optional[Path]
    signature_command: Optional[str]
    actor: Optional[str] = None
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
