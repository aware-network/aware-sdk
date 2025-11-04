"""Pydantic models describing release metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Checksum(BaseModel):
    sha256: str = Field(..., description="SHA-256 checksum for the bundle archive.")

    model_config = ConfigDict(extra="forbid")


class ProviderInfo(BaseModel):
    version: str
    source: Optional[str] = Field(default=None, description="Provider wheel or archive name.")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class BundleManifest(BaseModel):
    channel: str
    version: str
    built_at: datetime
    platform: str
    checksum: Checksum
    providers: Dict[str, ProviderInfo] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    python: Optional[str] = Field(default=None, description="Python runtime version used for the bundle.")

    model_config = ConfigDict(extra="forbid")


class ReleaseIndexEntry(BaseModel):
    channel: str
    version: str
    url: HttpUrl
    checksum: Checksum
    released_at: datetime
    notes: Optional[str] = None
    min_studio: Optional[str] = Field(default=None, description="Minimum Studio version compatible with the bundle.")

    model_config = ConfigDict(extra="forbid")


class ReleaseIndex(BaseModel):
    entries: List[ReleaseIndexEntry] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
