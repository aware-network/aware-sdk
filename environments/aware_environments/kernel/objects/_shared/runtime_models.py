"""Shared runtime models used across kernel objects."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class RuntimeModel(BaseModel):
    """Base model that normalises datetime and path fields."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    def model_dump_json_ready(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    def json_dict(self) -> Dict[str, Any]:
        return self.model_dump_json_ready()

    @staticmethod
    @staticmethod
    def _serialise_datetime(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class RuntimeEvent(RuntimeModel):
    event_id: str
    event_type: str
    timestamp: datetime
    path: Path
    summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "RuntimeModel",
    "RuntimeEvent",
]
