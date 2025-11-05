"""Pydantic models describing release artifacts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from aware_release.schemas.release import BundleManifest, Checksum, ProviderInfo


class ReleaseBundleArtifact(BaseModel):
    """Metadata describing a built release bundle."""

    archive_path: Path = Field(..., description="Final archive path relative to workspace when possible.")
    manifest_path: Path = Field(..., description="Final manifest path relative to workspace when possible.")
    channel: str
    version: str
    platform: str
    checksum: str
    dependencies: List[str] = Field(default_factory=list)
    providers: List[str] = Field(default_factory=list)
    built_at: datetime


class ReleaseLockArtifact(BaseModel):
    """Metadata describing a generated dependency lock file."""

    path: Path = Field(..., description="Path to the generated lock file.")
    platform: str = Field(..., description="Target platform identifier.")
    python_version: Optional[str] = Field(
        default=None, description="Optional Python version constraint used for resolution."
    )
    requirements: List[str] = Field(default_factory=list, description="Resolved requirements present in the lock.")
    generated_at: datetime = Field(..., description="Timestamp when the lock content was generated (UTC).")


class ReleaseUploadSummary(BaseModel):
    """Summary of the upload phase during publish."""

    adapter: str
    status: str
    url: Optional[str] = None
    details: Dict[str, object] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)


class ReleaseJournalEntry(BaseModel):
    """Structured journal entry describing a side-effect of publish."""

    action: str
    status: str
    timestamp: datetime
    metadata: Dict[str, object] = Field(default_factory=dict)


class ReleasePublishOutcome(BaseModel):
    """Aggregated publish outcome returned alongside an operation plan."""

    manifest_path: Path
    archive_path: Path
    checksum_match: bool
    index_path: Optional[Path] = None
    index_updated: bool = False
    signature_path: Optional[Path] = None
    upload: ReleaseUploadSummary
    logs: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    metadata: Dict[str, object] = Field(default_factory=dict)
    journal: List[ReleaseJournalEntry] = Field(default_factory=list)


class ReleaseChecksumModel(BaseModel):
    """Checksum details for manifest validation responses."""

    sha256: str

    @classmethod
    def from_release(cls, checksum: Checksum) -> "ReleaseChecksumModel":
        return cls(sha256=checksum.sha256)


class ReleaseProviderInfoModel(BaseModel):
    """Provider information embedded within a manifest."""

    version: str
    source: Optional[str] = None
    metadata: Dict[str, object] = Field(default_factory=dict)

    @classmethod
    def from_release(cls, info: ProviderInfo) -> "ReleaseProviderInfoModel":
        return cls(
            version=info.version,
            source=info.source,
            metadata=dict(info.metadata),
        )


class ReleaseManifestModel(BaseModel):
    """Manifest metadata surfaced during validation."""

    channel: str
    version: str
    built_at: datetime
    platform: str
    checksum: ReleaseChecksumModel
    providers: Dict[str, ReleaseProviderInfoModel]
    dependencies: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    python: Optional[str] = None

    @classmethod
    def from_release(cls, manifest: BundleManifest) -> "ReleaseManifestModel":
        return cls(
            channel=manifest.channel,
            version=manifest.version,
            built_at=manifest.built_at,
            platform=manifest.platform,
            checksum=ReleaseChecksumModel.from_release(manifest.checksum),
            providers={
                slug: ReleaseProviderInfoModel.from_release(info)
                for slug, info in manifest.providers.items()
            },
            dependencies=list(manifest.dependencies),
            notes=manifest.notes,
            python=manifest.python,
        )


class ReleaseManifestValidation(BaseModel):
    """Validation result for a release manifest."""

    manifest_path: Path
    valid: bool
    checksum_match: Optional[bool] = None
    errors: List[str] = Field(default_factory=list)
    manifest: Optional[ReleaseManifestModel] = None


__all__ = [
    "ReleaseBundleArtifact",
    "ReleaseLockArtifact",
    "ReleaseUploadSummary",
    "ReleaseJournalEntry",
    "ReleasePublishOutcome",
    "ReleaseChecksumModel",
    "ReleaseProviderInfoModel",
    "ReleaseManifestModel",
    "ReleaseManifestValidation",
]
