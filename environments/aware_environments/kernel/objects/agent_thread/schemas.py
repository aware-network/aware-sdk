"""Pydantic schemas for agent thread kernel routines."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AgentThreadDocument(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    is_main: Optional[bool] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    agent_process_id: Optional[str] = Field(default=None, alias="agent_process_id")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"extra": "allow", "populate_by_name": True}


class AgentProcessThreadMetadata(BaseModel):
    id: UUID
    actor_id: UUID
    agent_process_id: UUID
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow", "populate_by_name": True}


class AgentProcessMetadata(BaseModel):
    agent_id: UUID

    model_config = {"extra": "allow"}


class AgentMetadata(BaseModel):
    identity_id: Optional[UUID] = None
    id: Optional[UUID] = None

    model_config = {"extra": "allow"}


class AgentThreadLoginSession(BaseModel):
    session_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class AgentThreadLoginResult(BaseModel):
    agent: str
    process: str
    thread: str
    provider: str
    terminal_id: Optional[str] = None
    session: AgentThreadLoginSession
    descriptor_path: Optional[str] = None
    participants_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    env: Optional[Dict[str, Any]] = None
    provider_metadata: Optional[Dict[str, Any]] = None
    receipts: Optional[List[Dict[str, Any]]] = None
    journal: Optional[List[Dict[str, Any]]] = None

    model_config = {"extra": "allow"}


__all__ = [
    "AgentThreadDocument",
    "AgentProcessThreadMetadata",
    "AgentProcessMetadata",
    "AgentMetadata",
    "AgentThreadLoginSession",
    "AgentThreadLoginResult",
]
