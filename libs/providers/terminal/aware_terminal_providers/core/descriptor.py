"""Terminal provider descriptor models and helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, HttpUrl, Field, ConfigDict


DESCRIPTOR_ROOT = Path.home() / ".aware" / "threads"


class ProviderReleaseNotesModel(BaseModel):
    summary: str
    url: Optional[HttpUrl] = None
    source: Optional[str] = None
    fetched_at: Optional[str] = None


class ProviderDescriptorModel(BaseModel):
    slug: str
    session_id: str
    version: Optional[str] = None
    channel: Optional[str] = None
    binary_path: Optional[str] = None
    release_notes: Optional[ProviderReleaseNotesModel] = None
    updated_at: Optional[str] = None
    env: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class ProviderDescriptor(BaseModel):
    provider: ProviderDescriptorModel


def _descriptor_path(thread_id: str, terminal_id: str) -> Path:
    return DESCRIPTOR_ROOT / thread_id / "terminals" / f"{terminal_id}.json"


def load_provider_descriptor(thread_id: str, terminal_id: str) -> Optional[ProviderDescriptor]:
    path = _descriptor_path(thread_id, terminal_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProviderDescriptor.model_validate(data)
    except Exception:
        return None


def save_provider_descriptor(thread_id: str, terminal_id: str, descriptor: ProviderDescriptor) -> None:
    path = _descriptor_path(thread_id, terminal_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(descriptor.model_dump_json(indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
