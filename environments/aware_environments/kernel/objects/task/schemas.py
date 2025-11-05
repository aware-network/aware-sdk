"""Pydantic schemas for task handlers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class TaskStatusPlanPayload(BaseModel):
    project: str
    task: str
    previous_status: str
    new_status: str
    move_required: bool
    from_path: str
    to_path: str
    overview_path: str
    overview_metadata: Dict[str, object] = Field(default_factory=dict)
    overview_body: str
    backlog: Optional[Dict[str, str]] = None
    message: str
    timestamp: str

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class TaskListEntry(BaseModel):
    id: str
    uuid: Optional[str] = None
    slug: str
    project: str
    task: str
    title: str
    status: str
    priority: Optional[str] = None
    updated: Optional[str] = None
    path: str
    repository_index: Optional[Dict[str, object]] = None


class TaskListPayload(BaseModel):
    tasks: Tuple[TaskListEntry, ...] = Field(default_factory=tuple)


class TaskPathEntry(BaseModel):
    key: str
    path: str
    is_root: bool = False


class TaskPanePayload(BaseModel):
    task_id: str
    project_path: str
    task_slug: str
    task_manifest_path: str
    repository_id: str
    repository_root_path: str
    paths: List[TaskPathEntry] = Field(default_factory=list)
    hash: str
    updated_at: str
    status: Optional[str] = None
    priority: Optional[str] = None
    directories: Dict[str, str] = Field(default_factory=dict)


class TaskPaneManifest(BaseModel):
    pane_kind: str = "task"
    branch_id: str
    manifest_version: int = 4
    payload: TaskPanePayload


class TaskBranchData(BaseModel):
    branch_id: str
    id: str
    pane_kind: str = "task"
    name: Optional[str] = None
    is_main: bool = False
    created_at: datetime
    updated_at: datetime
    thread_branch_id: str
    thread_id: str
    object_instance_graph_id: Optional[str] = None


class TaskThreadBinding(BaseModel):
    task_id: str
    task_slug: str
    project_slug: str
    task_manifest_path: str


class TaskPaneBundle(BaseModel):
    branch: TaskBranchData
    pane_manifest: TaskPaneManifest
    task_binding: TaskThreadBinding
    manifest_version: int = 4
    branch_path: Optional[Path] = None
    pane_manifest_path: Optional[Path] = None


__all__ = [
    "TaskStatusPlanPayload",
    "TaskListEntry",
    "TaskListPayload",
    "TaskPathEntry",
    "TaskPanePayload",
    "TaskPaneManifest",
    "TaskBranchData",
    "TaskThreadBinding",
    "TaskPaneBundle",
]
