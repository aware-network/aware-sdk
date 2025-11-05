"""Pydantic schemas for the thread object."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, Union
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from .._shared.runtime_models import RuntimeModel


class ThreadEntry(RuntimeModel):
    process_slug: str
    thread_slug: str
    directory: Path
    thread_id: Optional[str] = None
    process_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    is_main: bool = False
    branch_count: int = 0
    pane_kinds: Tuple[str, ...] = ()
    conversation_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ThreadParticipantType(str, Enum):
    AGENT = "agent"
    HUMAN = "human"
    ORGANIZATION = "organization"
    SERVICE = "service"


class ThreadParticipantStatus(str, Enum):
    ATTACHED = "attached"
    DETACHED = "detached"
    RELEASED = "released"
    ERRORED = "errored"
    PENDING = "pending"


class ThreadParticipantRole(str, Enum):
    EXECUTOR = "executor"
    OBSERVER = "observer"
    CONTROLLER = "controller"
    OTHER = "other"


class ThreadParticipantSessionState(str, Enum):
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class ThreadParticipantIdentityAgent(RuntimeModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["agent"] = "agent"
    agent_process_thread_id: UUID
    agent_process_id: UUID
    agent_id: UUID
    identity_id: UUID
    actor_id: UUID
    slug: Optional[str] = None


class ThreadParticipantIdentityHuman(RuntimeModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["human"] = "human"
    human_id: UUID
    identity_id: UUID
    actor_id: UUID
    handle: Optional[str] = None


class ThreadParticipantIdentityOrganization(RuntimeModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["organization"] = "organization"
    organization_id: UUID
    identity_id: UUID
    actor_id: UUID
    slug: Optional[str] = None


class ThreadParticipantIdentityService(RuntimeModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["service"] = "service"
    service_id: UUID
    provider: str
    identity_id: Optional[UUID] = None


ThreadParticipantIdentity = Union[
    ThreadParticipantIdentityAgent,
    ThreadParticipantIdentityHuman,
    ThreadParticipantIdentityOrganization,
    ThreadParticipantIdentityService,
]


class ThreadParticipantSession(RuntimeModel):
    model_config = ConfigDict(extra="forbid")

    session_id: Optional[str] = None
    daemon_pid: Optional[int] = None
    transport: Optional[str] = None
    state: ThreadParticipantSessionState = ThreadParticipantSessionState.UNKNOWN
    tmux_window: Optional[str] = None
    socket_path: Optional[str] = None


class ThreadParticipant(RuntimeModel):
    model_config = ConfigDict(extra="forbid")

    participant_id: str
    type: ThreadParticipantType
    role: ThreadParticipantRole = ThreadParticipantRole.EXECUTOR
    status: ThreadParticipantStatus = ThreadParticipantStatus.ATTACHED
    identity: ThreadParticipantIdentity
    last_seen: Optional[datetime] = None
    session: ThreadParticipantSession = Field(default_factory=ThreadParticipantSession)
    metadata: Dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_identity_type(self) -> "ThreadParticipant":
        identity_type = getattr(self.identity, "type", None)
        if identity_type is None:
            return self
        if isinstance(self.type, ThreadParticipantType):
            type_value = self.type.value
        else:
            type_value = str(self.type)
        if type_value != identity_type:
            raise ValueError(
                f"Participant identity type '{identity_type}' does not match participant type '{type_value}'."
            )
        return self


class ThreadParticipantsManifest(RuntimeModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    thread_id: str
    process_slug: str
    updated_at: datetime
    participants: List[ThreadParticipant] = Field(default_factory=list)


__all__ = [
    "ThreadEntry",
    "ThreadParticipant",
    "ThreadParticipantsManifest",
    "ThreadParticipantIdentity",
    "ThreadParticipantIdentityAgent",
    "ThreadParticipantIdentityHuman",
    "ThreadParticipantIdentityOrganization",
    "ThreadParticipantIdentityService",
    "ThreadParticipantRole",
    "ThreadParticipantSession",
    "ThreadParticipantSessionState",
    "ThreadParticipantStatus",
    "ThreadParticipantType",
]
