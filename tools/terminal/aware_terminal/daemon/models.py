from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator, field_serializer


def _coerce_utc(value: datetime | str | None, *, default: Optional[datetime] = None) -> Optional[datetime]:
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    else:
        parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _encode_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.astimezone(timezone.utc)
    text = normalized.isoformat()
    if text.endswith("+00:00"):
        text = text[:-6] + "Z"
    return text


class SessionRecord(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    session_id: str = Field(alias="sessionId")
    tmux_window: str = Field(alias="tmuxWindow")
    shell: str = Field(default="/bin/bash")
    cwd: Path
    created_at: datetime = Field(alias="createdAt", default_factory=_utc_now)
    last_active_at: Optional[datetime] = Field(alias="lastActiveAt", default=None)
    start_script: Optional[str] = Field(alias="startScript", default=None)
    terminal_id: Optional[str] = Field(alias="terminalId", default=None)
    apt_id: Optional[str] = Field(alias="aptId", default=None)
    provider: Optional[str] = None
    command: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None

    @field_validator("created_at", "last_active_at", mode="before")
    @classmethod
    def _ensure_datetime(cls, value):
        return _coerce_utc(value)

    @field_validator("cwd", mode="before")
    @classmethod
    def _ensure_path(cls, value):
        if isinstance(value, Path):
            return value
        return Path(value or ".")

    @field_serializer("cwd")
    def _serialize_cwd(self, value: Path) -> str:
        return str(value)

    @field_serializer("created_at", "last_active_at")
    def _serialize_datetimes(self, value: Optional[datetime]) -> Optional[str]:
        return _encode_datetime(value)

    @field_serializer("env")
    def _serialize_env(self, value: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        return value or None

    def as_dict(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class Manifest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    thread: str
    socket_path: Path = Field(alias="socketPath")
    sessions: List[SessionRecord] = Field(default_factory=list)
    protocol_version: int = Field(alias="protocolVersion", default=1)
    updated_at: datetime = Field(alias="updatedAt", default_factory=_utc_now)

    @field_validator("socket_path", mode="before")
    @classmethod
    def _ensure_socket_path(cls, value):
        if isinstance(value, Path):
            return value
        return Path(value or "")

    @field_validator("updated_at", mode="before")
    @classmethod
    def _ensure_updated_at(cls, value):
        return _coerce_utc(value, default=_utc_now())

    @field_serializer("socket_path")
    def _serialize_socket_path(self, value: Path) -> str:
        return str(value)

    @field_serializer("updated_at")
    def _serialize_updated(self, value: datetime) -> Optional[str]:
        return _encode_datetime(value)

    def as_dict(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class ProtocolMessage(TypedDict, total=False):
    id: str
    type: str
    payload: Dict[str, Any]
    ok: bool
    error: str
