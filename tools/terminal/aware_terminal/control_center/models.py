from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, List
from pathlib import Path


@dataclass(frozen=True)
class EnvironmentInfo:
    id: str
    name: str
    slug: str
    repo_path: Path


@dataclass(frozen=True)
class ProcessInfo:
    id: str
    name: str
    slug: str
    environment_id: str


@dataclass(frozen=True)
class ThreadInfo:
    id: str
    name: str
    slug: str
    process_id: str
    environment_id: str
    main: bool = False
    branch_title: Optional[str] = None


@dataclass(frozen=True)
class ThreadStatus:
    thread_id: str
    last_event_timestamp: Optional[datetime]
    state: str
    summary: str


@dataclass(frozen=True)
class DocumentDescriptor:
    projection: str
    channel: str
    label: Optional[str] = None


@dataclass(frozen=True)
class ThreadEvent:
    id: str
    thread_id: str
    timestamp: datetime
    descriptor: DocumentDescriptor
    change_type: str
    doc_path: Path
    metadata: dict
    reviewed: bool = False


@dataclass(frozen=True)
class ThreadDoc:
    event_id: str
    content: str


class ControlDataProvider(Protocol):
    def list_environments(self) -> List[EnvironmentInfo]:
        ...

    def list_processes(self, environment_id: str) -> List[ProcessInfo]:
        ...

    def list_threads(self, process_id: str) -> List[ThreadInfo]:
        ...

    def get_thread_status(self, thread_id: str) -> ThreadStatus:
        ...

    def list_thread_events(self, thread_id: str, since: Optional[datetime] = None) -> List[ThreadEvent]:
        ...

    def get_event_doc(self, event_id: str) -> ThreadDoc:
        ...

    def mark_event_reviewed(self, event_id: str, reviewed: bool) -> None:
        ...
