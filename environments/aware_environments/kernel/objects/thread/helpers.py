"""Helper utilities for thread branch and manifest hydration."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple, List

from .schemas import ThreadEntry
from ..task.schemas import (
    TaskBranchData,
    TaskPaneBundle,
    TaskPaneManifest,
    TaskPanePayload,
    TaskPathEntry,
    TaskThreadBinding,
)


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _default_projects_root(entry: ThreadEntry) -> Path:
    docs_runtime_root = entry.directory.parents[3]
    docs_root = docs_runtime_root.parent
    return (docs_root / "projects").resolve()


def _load_task_index_entry(projects_root: Path, identifier: str) -> Dict[str, object]:
    if "/" not in identifier:
        raise ValueError("--task must be <project>/<task-slug>.")
    project_slug, task_slug = identifier.split("/", 1)
    index_path = projects_root / project_slug / "tasks" / ".index.json"
    if not index_path.exists():
        raise ValueError(
            f"Task index '{index_path}' not found. "
            "Run `project task-index-refresh` before binding the task pane."
        )
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Task index '{index_path}' is invalid JSON: {exc}") from exc
    if isinstance(data, dict):
        entries = data.get("tasks") or []
    else:
        entries = data
    if not isinstance(entries, list):
        raise ValueError(f"Unexpected task index structure in '{index_path}'.")
    for entry in entries:
        if isinstance(entry, dict) and entry.get("slug") == task_slug:
            entry["project_slug"] = project_slug
            return entry
    raise ValueError(f"Task slug '{task_slug}' not found in '{index_path}'.")


def _ensure_project_path(projects_root: Path, project_slug: str) -> str:
    return str((projects_root / project_slug).resolve())


def _build_task_paths(entry: Dict[str, object]) -> Tuple[list, str]:
    paths = entry.get("paths") or []
    if isinstance(paths, list):
        coerced = []
        for item in paths:
            if isinstance(item, dict):
                coerced.append(
                    {
                        "key": item.get("key"),
                        "path": item.get("path"),
                        "is_root": bool(item.get("is_root")),
                    }
                )
            else:
                coerced.append(item)
    else:
        coerced = []
    manifest_path = entry.get("manifest_path")
    if not manifest_path and entry.get("directories"):
        directories = entry["directories"]
        if isinstance(directories, dict):
            manifest_path = (
                directories.get("overview")
                or directories.get("task_root")
            )
    return coerced, manifest_path or ""


def build_task_branch_bundle(
    entry: ThreadEntry,
    *,
    task_identifier: str,
    projects_root: Optional[str] = None,
) -> TaskPaneBundle:
    projects_root_path = (
        Path(projects_root).expanduser().resolve()
        if projects_root
        else _default_projects_root(entry)
    )
    index_entry = _load_task_index_entry(projects_root_path, task_identifier)

    project_slug = index_entry.get("project_slug") or ""
    task_slug = index_entry.get("slug") or task_identifier.split("/", 1)[-1]
    task_id = index_entry.get("task_id")
    if not task_id:
        raise ValueError(
            f"Task '{task_identifier}' is missing the canonical task_id in the index. "
            "Refresh the task index before binding the pane."
        )
    repository_id = index_entry.get("repository_id")
    repository_root_path = index_entry.get("repository_root_path") or "."

    directories = index_entry.get("directories") or {}
    paths, manifest_path = _build_task_paths(index_entry)
    if not manifest_path:
        raise ValueError(
            f"Task '{task_identifier}' is missing a manifest path in the index."
        )

    status = (index_entry.get("metadata") or {}).get("status") or index_entry.get("status")
    priority = (index_entry.get("metadata") or {}).get("priority") or index_entry.get("priority")
    hash_value = index_entry.get("hash")
    updated_at_value = index_entry.get("updated_at")
    updated_at = _parse_iso_datetime(updated_at_value) or datetime.now(timezone.utc)

    branch_name = f"{(entry.title or entry.thread_slug).strip()} Task"
    branch_created = entry.created_at or updated_at

    object_instance_graph_id = None
    if repository_id:
        object_instance_graph_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"aware://repository/{repository_id}/task/{task_id}",
            )
        )

    branch = {
        "branch_id": task_id,
        "id": task_id,
        "pane_kind": "task",
        "name": branch_name,
        "is_main": False,
        "created_at": branch_created.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "thread_branch_id": task_id,
        "thread_id": entry.thread_id or entry.thread_slug,
    }
    if object_instance_graph_id:
        branch["object_instance_graph_id"] = object_instance_graph_id

    path_models: List[TaskPathEntry] = [TaskPathEntry.model_validate(entry) for entry in paths]
    pane_payload = TaskPanePayload(
        task_id=task_id,
        project_path=_ensure_project_path(projects_root_path, project_slug),
        task_slug=task_slug,
        task_manifest_path=manifest_path,
        repository_id=repository_id,
        repository_root_path=repository_root_path,
        paths=path_models,
        hash=hash_value,
        updated_at=updated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        status=status,
        priority=priority,
        directories=directories if isinstance(directories, dict) else {},
    )

    pane_manifest = TaskPaneManifest(
        branch_id=task_id,
        payload=pane_payload,
    )

    task_binding = TaskThreadBinding(
        task_id=task_id,
        task_slug=task_slug,
        project_slug=project_slug,
        task_manifest_path=manifest_path,
    )

    branch_model = TaskBranchData(
        branch_id=task_id,
        id=task_id,
        pane_kind="task",
        name=branch_name,
        is_main=False,
        created_at=branch_created.astimezone(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        thread_branch_id=task_id,
        thread_id=entry.thread_id or entry.thread_slug,
        object_instance_graph_id=object_instance_graph_id,
    )

    return TaskPaneBundle(
        branch=branch_model,
        pane_manifest=pane_manifest,
        task_binding=task_binding,
        manifest_version=4,
    )


def _find_docs_root(path: Path) -> Optional[Path]:
    resolved = path.resolve()
    for ancestor in resolved.parents:
        if ancestor.name == "docs":
            return ancestor
    return None


def _repo_relative_path(
    path: Path,
    *,
    runtime_root: Path,
    thread_directory: Path,
) -> str:
    resolved = path.resolve()
    candidates = []
    docs_root = _find_docs_root(thread_directory)
    if docs_root is not None:
        candidates.append(docs_root.parent)
    runtime_root = runtime_root.resolve()
    candidates.append(runtime_root)
    candidates.append(runtime_root.parent)  # docs/
    candidates.append(runtime_root.parent.parent if runtime_root.parent else None)
    candidates.append(thread_directory.resolve())
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return resolved.relative_to(candidate.resolve()).as_posix()
        except ValueError:
            continue
    return resolved.as_posix()


def build_conversation_branch_bundle(
    runtime_root: Path,
    entry: ThreadEntry,
    *,
    conversation_identifier: str,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    from ..conversation import handlers as conversation_handlers

    runtime_root = Path(runtime_root).resolve()
    list_entry = conversation_handlers.resolve(runtime_root, identifier=conversation_identifier)
    payload = conversation_handlers.document(
        runtime_root,
        process_slug=list_entry.process_slug,
        thread_slug=list_entry.thread_slug,
        conversation_slug=list_entry.slug,
    )

    metadata = payload.metadata.model_dump(mode="json")
    conversation_id = metadata.get("conversation_id") or list_entry.slug

    now = datetime.now(timezone.utc)

    created_meta = metadata.get("created_at")
    if isinstance(created_meta, datetime):
        created_dt = created_meta
    else:
        created_dt = _parse_iso_datetime(created_meta) or now

    updated_meta = metadata.get("updated_at")
    if isinstance(updated_meta, datetime):
        updated_dt = updated_meta
    else:
        updated_dt = _parse_iso_datetime(updated_meta) or created_dt

    branch = {
        "branch_id": conversation_id,
        "id": conversation_id,
        "pane_kind": "conversation",
        "name": metadata.get("title") or list_entry.slug,
        "is_main": True,
        "created_at": created_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "updated_at": updated_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "thread_branch_id": conversation_id,
        "thread_id": entry.thread_id or entry.thread_slug,
    }

    source_path = _repo_relative_path(
        payload.path,
        runtime_root=runtime_root,
        thread_directory=entry.directory,
    )

    pane_manifest = {
        "pane_kind": "conversation",
        "branch_id": conversation_id,
        "manifest_version": 1,
        "payload": {
            "conversation_id": metadata.get("conversation_id"),
            "source": source_path,
            "opg_name": "ConversationOPG",
        },
    }

    return branch, pane_manifest
