"""Pydantic models for provider release manifests."""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, HttpUrl, Field, ConfigDict


class ReleaseNotesModel(BaseModel):
    summary: str = Field(..., description="Plain-text summary of latest changes.")
    url: Optional[HttpUrl] = Field(
        default=None,
        description="Link to full release notes/changelog entry.",
    )
    source: Optional[str] = Field(
        default=None,
        description="Source identifier (e.g., github_release, github_changelog, manual).",
    )
    fetched_at: Optional[str] = Field(
        default=None,
        description="UTC timestamp when release notes were fetched.",
    )


class ChannelInfoModel(BaseModel):
    version: str = Field(..., description="Validated provider version for the channel.")
    npm_tag: Optional[str] = Field(
        default=None,
        description="NPM dist-tag associated with this channel.",
    )
    updated_at: Optional[str] = Field(
        default=None,
        description="UTC timestamp when manifest entry was last updated.",
    )
    release_notes: Optional[ReleaseNotesModel] = Field(
        default=None,
        description="Optional release note metadata.",
    )

    model_config = ConfigDict(extra="allow")


class ProviderManifestModel(BaseModel):
    provider: str = Field(..., description="Provider slug (e.g., codex, claude-code).")
    channels: Dict[str, ChannelInfoModel] = Field(
        default_factory=dict,
        description="Channel entries keyed by channel slug (latest, preview, nightly, ...).",
    )
