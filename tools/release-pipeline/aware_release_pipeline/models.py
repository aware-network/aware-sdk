from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass(slots=True)
class CliPrepareResult:
    archive_path: str
    manifest_path: str
    manifest: Dict[str, object]
    lock_path: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "archive_path": self.archive_path,
            "manifest_path": self.manifest_path,
            "manifest": self.manifest,
        }
        if self.lock_path:
            payload["lock_path"] = self.lock_path
        return payload


@dataclass(slots=True)
class CliPublishUpload:
    adapter: str
    status: str
    url: Optional[str]
    details: Dict[str, object]
    logs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "adapter": self.adapter,
            "status": self.status,
            "url": self.url,
            "details": self.details,
            "logs": self.logs,
        }


@dataclass(slots=True)
class CliPublishResult:
    manifest_path: str
    archive_path: str
    checksum_match: bool
    index_path: Optional[str]
    index_updated: bool
    signature_path: Optional[str]
    upload: CliPublishUpload
    logs: List[str]
    next_steps: List[str]
    metadata: Dict[str, object]
    def to_dict(self) -> Dict[str, object]:
        return {
            "manifest_path": self.manifest_path,
            "archive_path": self.archive_path,
            "checksum_match": self.checksum_match,
            "index_path": self.index_path,
            "index_updated": self.index_updated,
            "signature_path": self.signature_path,
            "upload": self.upload.to_dict(),
            "logs": self.logs,
            "next_steps": self.next_steps,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class RulesRenderResult:
    cli_version: str
    rules_root: str
    manifest_path: str
    rules: List[str]
    update_current: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "cli_version": self.cli_version,
            "rules_root": self.rules_root,
            "manifest_path": self.manifest_path,
            "rules": self.rules,
            "update_current": self.update_current,
        }


@dataclass(slots=True)
class ProviderRefreshResult:
    manifest_paths: List[str]
    providers_changed: List[str]
    timestamp: datetime
    logs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "manifest_paths": self.manifest_paths,
            "providers_changed": self.providers_changed,
            "timestamp": self.timestamp.isoformat(),
            "logs": self.logs,
        }


@dataclass(slots=True)
class ProviderValidationIssue:
    manifest: str
    message: str
    level: str = "error"

    def to_dict(self) -> Dict[str, object]:
        return {
            "manifest": self.manifest,
            "message": self.message,
            "level": self.level,
        }


@dataclass(slots=True)
class ProviderValidationResult:
    manifest_paths: List[str]
    issues: List[ProviderValidationIssue] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, object]:
        return {
            "manifest_paths": self.manifest_paths,
            "issues": [issue.to_dict() for issue in self.issues],
            "timestamp": self.timestamp.isoformat(),
        }
