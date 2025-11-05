"""Pydantic schemas for project handlers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class _ProjectBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class ProjectTaskSummary(_ProjectBaseModel):
    id: str
    uuid: Optional[str] = None
    slug: str
    title: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    path: Path


class ProjectStatusPayload(_ProjectBaseModel):
    id: str
    uuid: Optional[str] = None
    slug: str
    title: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_modified: Optional[str] = None
    task_count: int
    tasks: List[ProjectTaskSummary] = Field(default_factory=list)
    metadata: Dict[str, object] = Field(default_factory=dict)
    path: Path
    overview_path: Path


class ProjectTasksPayload(_ProjectBaseModel):
    project: str
    tasks: List[ProjectTaskSummary] = Field(default_factory=list)


class ProjectListEntry(_ProjectBaseModel):
    id: str
    uuid: Optional[str] = None
    slug: str
    title: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    task_count: int
    last_modified: Optional[str] = None
    path: Path


class ProjectTaskPath(_ProjectBaseModel):
    key: str
    path: str
    is_root: bool = False


class ProjectTaskIndexEntry(_ProjectBaseModel):
    task_id: str
    slug: str
    status: str
    task_root: str
    manifest_path: Optional[str] = None
    directories: Dict[str, str] = Field(default_factory=dict)
    repository_id: str
    repository_root_path: str
    paths: List[ProjectTaskPath] = Field(default_factory=list)
    hash: str
    metadata: Dict[str, object] = Field(default_factory=dict)
    updated_at: datetime


__all__ = [
    "ProjectListEntry",
    "ProjectStatusPayload",
    "ProjectTaskIndexEntry",
    "ProjectTaskPath",
    "ProjectTaskSummary",
    "ProjectTasksPayload",
]
