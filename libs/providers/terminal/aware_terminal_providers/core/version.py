"""Helper utilities for provider release metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .manifest import ProviderManifestModel

_PROVIDERS_ROOT = Path(__file__).resolve().parents[1] / "providers"


@dataclass(frozen=True)
class ChannelInfo:
    version: Optional[str]
    npm_tag: Optional[str]
    updated_at: Optional[str]
    release_notes: Optional[Dict[str, Any]]
    extra: Dict[str, Any]


def _manifest_path(provider: str) -> Path:
    path = _PROVIDERS_ROOT / provider / "releases.json"
    if path.exists():
        return path
    alt = provider.replace("-", "_")
    alt_path = _PROVIDERS_ROOT / alt / "releases.json"
    return alt_path


def load_manifest(provider: str) -> ProviderManifestModel:
    path = _manifest_path(provider)
    if not path.exists():
        raise FileNotFoundError(
            f"Release manifest not found for provider '{provider}' at {path}"
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}") from exc
    try:
        return ProviderManifestModel.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"Manifest for provider '{provider}' failed validation: {exc}") from exc


def get_channel_info(provider: str, channel: str = "latest") -> ChannelInfo:
    manifest = load_manifest(provider)
    channel_model = manifest.channels.get(channel)
    if channel_model is None:
        return ChannelInfo(version=None, npm_tag=None, updated_at=None, release_notes=None, extra={})

    release_notes = None
    if channel_model.release_notes is not None:
        release_notes = channel_model.release_notes.model_dump()

    extra = channel_model.model_dump(
        exclude={"version", "npm_tag", "updated_at", "release_notes"},
        exclude_unset=True,
    )
    return ChannelInfo(
        version=channel_model.version,
        npm_tag=channel_model.npm_tag,
        updated_at=channel_model.updated_at,
        release_notes=release_notes,
        extra=extra,
    )


def get_supported_version(provider: str, channel: str = "latest") -> Optional[str]:
    info = get_channel_info(provider, channel=channel)
    return info.version
