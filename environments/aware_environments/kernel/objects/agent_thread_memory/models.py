"""Pydantic models describing agent thread memory artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class WorkingMemoryAuthor(BaseModel):
    agent: str
    process: str
    thread: str


class WorkingMemoryDocument(BaseModel):
    id: str
    author: WorkingMemoryAuthor
    updated: datetime
    created: Optional[datetime] = None
    content: str
    path: Optional[str] = None


class EpisodicEntryHeader(BaseModel):
    id: str
    author: WorkingMemoryAuthor
    timestamp: datetime
    session_type: Optional[str] = None
    significance: Optional[str] = None


class EpisodicEntry(BaseModel):
    header: EpisodicEntryHeader
    body: str
    path: str


class MemorySummary(BaseModel):
    working: Optional[WorkingMemoryDocument] = None
    episodic: List[EpisodicEntry] = Field(default_factory=list)


__all__ = [
    "WorkingMemoryAuthor",
    "WorkingMemoryDocument",
    "EpisodicEntryHeader",
    "EpisodicEntry",
    "MemorySummary",
]
