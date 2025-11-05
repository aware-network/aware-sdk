"""Pydantic schemas for the process object."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from .._shared.runtime_models import RuntimeModel


class ProcessEntry(RuntimeModel):
    slug: str
    directory: Path
    process_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority_level: Optional[str] = None
    status: Optional[str] = None
    thread_count: int = 0
    latest_backlog_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


__all__ = ["ProcessEntry"]
