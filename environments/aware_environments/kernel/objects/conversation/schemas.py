"""Pydantic schemas for conversation read payloads."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConversationBaseModel(BaseModel):
    """Base conversation model with permissive config for filesystem payloads."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class ConversationParticipant(ConversationBaseModel):
    id: str = ""
    actor_id: Optional[str] = None
    actor_type: Optional[str] = None
    source_id: Optional[str] = None
    type: str = "member"
    role: str = "member"
    name: str = ""
    handle: str = ""

    @model_validator(mode="after")
    def _synchronise_identifier_fields(self) -> "ConversationParticipant":
        actor_id = (self.actor_id or "").strip()
        if not actor_id:
            return self
        try:
            actor_uuid = str(UUID(actor_id)).lower()
        except (ValueError, TypeError):
            actor_uuid = actor_id.lower()
        self.actor_id = actor_uuid
        if not self.id or self.id.strip().lower() != actor_uuid:
            self.id = actor_uuid
        if not self.actor_type:
            self.actor_type = self.type
        return self


class ConversationMetadata(ConversationBaseModel):
    conversation_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    participants: List[ConversationParticipant] = Field(default_factory=list)

    @field_validator("participants", mode="before")
    @classmethod
    def _coerce_participants(cls, value):
        if value is None:
            return []
        return value


class ConversationMessage(ConversationBaseModel):
    message_id: Optional[str] = None
    actor_id: str
    receiver_id: Optional[str] = None
    created_at: Optional[datetime] = None
    status: Optional[str] = None
    message_type: Optional[str] = None
    content: str = ""


class ConversationHistoryPayload(ConversationBaseModel):
    conversation: str
    metadata: ConversationMetadata
    messages: List[ConversationMessage] = Field(default_factory=list)
    path: Path
    markdown: Optional[str] = None


class ConversationDocumentPayload(ConversationBaseModel):
    metadata: ConversationMetadata
    body: str
    path: Path


class ConversationListEntry(ConversationBaseModel):
    id: str
    uuid: Optional[str] = None
    process_slug: str
    thread_slug: str
    slug: str
    conversation_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    participant_count: int = 0
    path: Path
    index_entry: Optional[dict[str, object]] = None


class ConversationAppendResult(ConversationBaseModel):
    message_id: str


class ConversationParticipantsResult(ConversationBaseModel):
    participants: List[ConversationParticipant]


class ConversationIndexRefreshThread(ConversationBaseModel):
    process_slug: str
    thread_slug: str
    path: Path
    entry_count: int = 0


class ConversationIndexRefreshResult(ConversationBaseModel):
    count: int
    threads: List[ConversationIndexRefreshThread] = Field(default_factory=list)


class ConversationRepairResult(ConversationBaseModel):
    updated: int
    skipped: int
    dry_run: bool = False
    conversations: List[str] = Field(default_factory=list)
    skipped_conversations: List[str] = Field(default_factory=list)
    receipts: Optional[List[dict[str, object]]] = None
    journal: Optional[List[dict[str, object]]] = None


__all__ = [
    "ConversationAppendResult",
    "ConversationDocumentPayload",
    "ConversationHistoryPayload",
    "ConversationIndexRefreshResult",
    "ConversationIndexRefreshThread",
    "ConversationListEntry",
    "ConversationMetadata",
    "ConversationMessage",
    "ConversationParticipant",
    "ConversationParticipantsResult",
    "ConversationRepairResult",
]
