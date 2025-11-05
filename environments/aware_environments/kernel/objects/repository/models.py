"""Repository index models shared across kernel + CLI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel


class RepositoryStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_count: Optional[int] = None
    directory_count: Optional[int] = None
    approx_size_bytes: Optional[int] = None


class RepositoryIndexEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_id: str
    workspace_root: str
    name: str
    project_slug: Optional[str] = None
    default_expanded_paths: List[str] = Field(default_factory=list)
    stats: Optional[RepositoryStats] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime

    def json_dict(self) -> Dict[str, Any]:
        payload = self.model_dump(mode="json")
        if isinstance(self.updated_at, datetime):
            payload["updated_at"] = (
                self.updated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            )
        return payload


class RepositoryIndex(RootModel[List[RepositoryIndexEntry]]):
    """Container for repository index entries."""


__all__ = ["RepositoryIndexEntry", "RepositoryStats", "RepositoryIndex"]
