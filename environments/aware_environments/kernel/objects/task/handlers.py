"""Kernel handlers for task lifecycle operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Sequence
from uuid import uuid4

from aware_environment.fs import (
    EnsureInstruction,
    MoveInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)
from .._shared.frontmatter import load_frontmatter, FrontmatterResult
from ..project.handlers import (
    _task_bucket,
    _task_directory,
    _default_task_overview,
    list_projects,
    project_tasks,
    build_task_index,
)
from ..project.schemas import ProjectTaskIndexEntry
from .write_plan import (
    _compose_document,
    _merge_body,
    TaskPlanResult,
    plan_task_backlog,
    plan_task_document,
    plan_task_overview,
)
from .schemas import TaskStatusPlanPayload, TaskListEntry, TaskListPayload


FINISHED_STATUSES = {"finished_succeeded", "finished_failed"}
ALLOWED_STATUSES = {"queued", "running"} | FINISHED_STATUSES


@dataclass(frozen=True)
class TaskStatusPlanResult:
    plan: OperationPlan
    payload: TaskStatusPlanPayload


def _normalize_status(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if normalized not in ALLOWED_STATUSES:
        raise ValueError(
            f"Unsupported task status '{value}'. Expected one of: {', '.join(sorted(ALLOWED_STATUSES))}."
        )
    return normalized


def _status_display_name(status: str) -> str:
    return status.replace("_", " ").replace("-", " ").title()


def _load_overview(task_dir: Path) -> tuple[Dict[str, object], str]:
    overview_path = task_dir / "OVERVIEW.md"
    if overview_path.exists():
        fm = load_frontmatter(overview_path)
        metadata = dict(fm.metadata)
        body = fm.body
    else:
        metadata = {}
        body = ""
    return metadata, body


def list_tasks(
    projects_root: Path,
    *,
    project_filter: Optional[Sequence[str]] = None,
    status_filter: Optional[Sequence[str]] = None,
) -> TaskListPayload:
    projects_root = Path(projects_root).resolve()
    project_filter_set = {value.lower() for value in project_filter or []}
    status_filter_list = list(status_filter or [])
    status_filter_set = {value.lower() for value in status_filter_list}

    entries: list[TaskListEntry] = []

    projects = list_projects(projects_root)
    for project_entry in projects:
        project_slug = project_entry.slug
        project_name = (
            project_entry.path.name if isinstance(project_entry.path, Path) else str(project_entry.path)
        )
        if project_filter_set and project_slug.lower() not in project_filter_set and project_name.lower() not in project_filter_set:
            continue

        index_entries = build_task_index(projects_root, project_slug=project_slug)
        index_map: Dict[str, ProjectTaskIndexEntry] = {entry.slug: entry for entry in index_entries}

        index_path = projects_root / project_slug / "tasks" / ".index.json"
        if index_path.exists():
            try:
                index_data = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                index_data = []
            if isinstance(index_data, list):
                for entry in index_data:
                    try:
                        model = ProjectTaskIndexEntry.model_validate(entry)
                    except Exception:  # pragma: no cover - ignore malformed entries
                        continue
                    index_map[model.slug] = model

        tasks_payload = project_tasks(
            projects_root,
            identifier=project_slug,
            status_filter=status_filter_list if status_filter_list else None,
        )
        for task in tasks_payload.tasks:
            status_value = task.status or ""
            if status_filter_set and status_value.lower() not in status_filter_set:
                continue
            slug_value = task.slug
            short_slug = slug_value.split("/", 1)[-1]
            repository_entry = index_map.get(short_slug) or index_map.get(slug_value)
            repository_index = None
            if repository_entry is not None:
                repository_index = repository_entry.model_dump(mode="json")
            path_str = str(task.path)
            entries.append(
                TaskListEntry(
                    id=slug_value,
                    uuid=task.uuid,
                    slug=slug_value,
                    project=project_slug,
                    task=short_slug,
                    title=task.title,
                    status=status_value,
                    priority=task.priority,
                    updated=task.updated_at,
                    path=path_str,
                    repository_index=repository_index,
                )
            )

    return TaskListPayload(tasks=tuple(entries))


def update_status_plan(
    projects_root: Path,
    *,
    project_slug: str,
    task_slug: str,
    target_status: str,
    reason: str = "",
    force: bool = False,
    author: Optional[Dict[str, str]] = None,
) -> TaskStatusPlanResult:
    projects_root = Path(projects_root).resolve()
    project_path = projects_root / project_slug
    if not project_path.exists():
        raise ValueError(f"Project '{project_slug}' not found under {projects_root}.")

    target_status_normalized = _normalize_status(target_status)

    # Determine current dir/status
    tasks_root = project_path / "tasks"
    possible_dirs = [
        tasks_root / task_slug,
        tasks_root / "_pending" / task_slug,
        tasks_root / "_completed" / task_slug,
    ]
    current_dir = next((path for path in possible_dirs if path.exists()), None)
    if current_dir is None:
        raise ValueError(f"Task '{task_slug}' not found in project '{project_slug}'.")

    bucket = ""
    relative_parts = current_dir.relative_to(tasks_root)
    if relative_parts.parts and relative_parts.parts[0] in {"_pending", "_completed"}:
        bucket = relative_parts.parts[0]
    current_status = "queued" if bucket == "_pending" else "running"
    if bucket == "_completed":
        current_status = "finished_succeeded"

    metadata, body = _load_overview(current_dir)
    current_status = metadata.get("status", current_status)
    current_status_normalized = _normalize_status(current_status)

    reason_text = reason.strip()
    if (
        target_status_normalized == current_status_normalized
        and not force
        and not reason_text
    ):
        raise ValueError(
            f"Task '{project_slug}/{task_slug}' already in status '{current_status_normalized}'."
        )

    target_dir = _task_directory(project_path, task_slug, target_status_normalized)
    move_required = current_dir.resolve() != target_dir.resolve()
    target_bucket = _task_bucket(target_status_normalized)

    now = datetime.now(timezone.utc)
    iso_now = now.isoformat().replace("+00:00", "Z")

    metadata.setdefault("id", task_slug)
    metadata.setdefault("slug", task_slug)
    metadata.setdefault("title", task_slug.replace("-", " ").title())
    metadata.setdefault("priority", metadata.get("priority", "medium"))
    metadata["status"] = target_status_normalized
    metadata["updated"] = iso_now
    if author is not None:
        metadata["author"] = dict(author)
    else:
        metadata["author"] = metadata.get("author", {})
    if target_status_normalized in FINISHED_STATUSES:
        metadata["completed"] = iso_now

    body_text = body.rstrip("\n")
    if reason_text:
        marker = "## Status Updates"
        display_status = _status_display_name(target_status_normalized)
        if marker not in body_text:
            if body_text:
                body_text = f"{body_text.rstrip()}\n\n{marker}\n\n"
            else:
                body_text = f"{marker}\n\n"
        elif not body_text.endswith("\n"):
            body_text = f"{body_text}\n"
        entry_line = f"- {iso_now} → {display_status}: {reason_text}"
        body_text = f"{body_text.rstrip()}\n{entry_line}\n"
    elif body_text:
        body_text = body_text.rstrip() + "\n"

    target_overview = target_dir / "OVERVIEW.md"
    overview_source = current_dir / "OVERVIEW.md"

    ensures: Dict[str, EnsureInstruction] = {}
    if move_required:
        ensures[str(target_dir.parent)] = EnsureInstruction(path=target_dir.parent)
    else:
        ensures[str(target_dir)] = EnsureInstruction(path=target_dir)

    moves: tuple[MoveInstruction, ...] = ()
    if move_required:
        moves = (
            MoveInstruction(
                src=current_dir,
                dest=target_dir,
                overwrite=False,
            ),
        )

    overview_instruction = WriteInstruction(
        path=target_overview,
        content=_compose_document(metadata, body_text),
        policy=OperationWritePolicy.MODIFIABLE,
        event="modified" if overview_source.exists() else "created",
        doc_type="overview",
        timestamp=now,
        metadata={
            "project": project_slug,
            "task": task_slug,
            "bucket": target_bucket,
        },
    )
    writes = [overview_instruction]

    backlog_payload = None
    if reason_text:
        summary = f"Status updated to {target_status_normalized}"
        entry_line = (
            f"- Status changed to {target_status_normalized} "
            f"({_status_display_name(target_status_normalized)}). Reason: {reason_text}"
        )
        backlog_dir_target = target_dir / "backlog"

        backlog_date = now.strftime("%Y-%m-%d")
        backlog_target_path = backlog_dir_target / f"{backlog_date}.md"
        backlog_source_path = (
            (current_dir / "backlog" / f"{backlog_date}.md")
            if move_required
            else backlog_target_path
        )

        author_data = dict(metadata.get("author", {}))
        if backlog_source_path.exists():
            fm = load_frontmatter(backlog_source_path)
            backlog_metadata = dict(fm.metadata)
            backlog_metadata.setdefault("id", backlog_metadata.get("id") or str(uuid4()))
            backlog_metadata.setdefault("title", backlog_metadata.get("title") or summary)
            backlog_metadata["slug"] = backlog_metadata.get("slug") or f"{task_slug}-backlog-{backlog_date}"
            backlog_metadata["updated"] = iso_now
            backlog_metadata["author"] = author_data
            if summary:
                backlog_metadata["summary"] = summary
            else:
                backlog_metadata.setdefault("summary", "")
            combined_body = _merge_body(fm.body, f"[{iso_now}]\n{entry_line.rstrip()}")
            backlog_event = "appended"
            backlog_content = _compose_document(backlog_metadata, combined_body)
        else:
            backlog_metadata = {
                "id": str(uuid4()),
                "title": summary,
                "slug": f"{task_slug}-backlog-{backlog_date}",
                "created": iso_now,
                "updated": iso_now,
                "author": author_data,
                "summary": summary,
            }
            backlog_event = "created"
            backlog_content = _compose_document(backlog_metadata, f"[{iso_now}]\n{entry_line.rstrip()}")

        writes.append(
            WriteInstruction(
                path=backlog_target_path,
                content=backlog_content,
                policy=OperationWritePolicy.APPEND_ENTRY,
                event=backlog_event,
                doc_type="backlog",
                timestamp=now,
                metadata=backlog_metadata,
            )
        )
        backlog_payload = {
            "summary": summary,
            "body": entry_line,
            "dir": str(backlog_dir_target),
        }

    payload = TaskStatusPlanPayload(
        project=project_slug,
        task=task_slug,
        previous_status=current_status_normalized,
        new_status=target_status_normalized,
        move_required=move_required,
        from_path=str(current_dir.relative_to(projects_root)),
        to_path=str(target_dir.relative_to(projects_root)),
        overview_path=str(target_overview.relative_to(projects_root)),
        overview_metadata=metadata,
        overview_body=body_text,
        backlog=backlog_payload,
        message=(
            f"{iso_now} status {current_status_normalized}->{target_status_normalized} "
            f"for {project_slug}/{task_slug}"
        ),
        timestamp=iso_now,
    )

    plan = OperationPlan(
        context=OperationContext(
            object_type="task",
            function="update-status",
            selectors={
                "project": project_slug,
                "task": task_slug,
                "project_slug": project_slug,
                "task_slug": task_slug,
                "task_bucket": target_bucket,
            },
        ),
        ensure_dirs=tuple(ensures.values()),
        moves=moves,
        writes=tuple(writes),
    )

    return TaskStatusPlanResult(plan=plan, payload=payload)


def update_status_handler(
    projects_root: Path,
    *,
    project_slug: str,
    task_slug: str,
    target_status: str,
    reason: str = "",
    force: bool = False,
    author: Optional[Dict[str, str]] = None,
) -> Dict[str, object]:
    result = update_status_plan(
        projects_root,
        project_slug=project_slug,
        task_slug=task_slug,
        target_status=target_status,
        reason=reason,
        force=force,
        author=author,
    )
    return result


def analysis_plan(
    projects_root: Path,
    *,
    project_slug: str,
    task_slug: str,
    task_bucket: Optional[str],
    title: str,
    slug: Optional[str],
    summary: str,
    content: str,
    author: Dict[str, str],
) -> TaskPlanResult:
    return plan_task_document(
        Path(projects_root),
        function_name="analysis",
        project_slug=project_slug,
        task_slug=task_slug,
        subdir="analysis",
        doc_type="analysis",
        title=title,
        slug=slug,
        summary=summary,
        content=content,
        author=author,
    )


def design_plan(
    projects_root: Path,
    *,
    project_slug: str,
    task_slug: str,
    task_bucket: Optional[str],
    title: str,
    slug: Optional[str],
    summary: str,
    content: str,
    author: Dict[str, str],
    version_bump: Optional[str] = None,
) -> TaskPlanResult:
    return plan_task_document(
        Path(projects_root),
        function_name="design",
        project_slug=project_slug,
        task_slug=task_slug,
        subdir="design",
        doc_type="design",
        title=title,
        slug=slug,
        summary=summary,
        content=content,
        author=author,
        version_bump=version_bump,
    )


def change_plan(
    projects_root: Path,
    *,
    project_slug: str,
    task_slug: str,
    task_bucket: Optional[str],
    title: str,
    slug: Optional[str],
    summary: str,
    content: str,
    author: Dict[str, str],
) -> TaskPlanResult:
    return plan_task_document(
        Path(projects_root),
        function_name="change",
        project_slug=project_slug,
        task_slug=task_slug,
        subdir="implementation/changes",
        doc_type="change",
        title=title,
        slug=slug,
        summary=summary,
        content=content,
        author=author,
    )


def backlog_plan(
    projects_root: Path,
    *,
    project_slug: str,
    task_slug: str,
    task_bucket: Optional[str],
    title: str,
    slug: Optional[str],
    summary: str,
    content: str,
    author: Dict[str, str],
) -> TaskPlanResult:
    return plan_task_backlog(
        Path(projects_root),
        function_name="backlog",
        project_slug=project_slug,
        task_slug=task_slug,
        title=title,
        slug=slug,
        summary=summary,
        content=content,
        author=author,
    )


def overview_plan(
    projects_root: Path,
    *,
    project_slug: str,
    task_slug: str,
    task_bucket: Optional[str],
    title: str,
    slug: Optional[str],
    summary: str,
    content: str,
    author: Dict[str, str],
) -> TaskPlanResult:
    return plan_task_overview(
        Path(projects_root),
        function_name="overview",
        project_slug=project_slug,
        task_slug=task_slug,
        title=title,
        slug=slug,
        summary=summary,
        content=content,
        author=author,
    )


__all__ = [
    "list_tasks",
    "TaskStatusPlanResult",
    "update_status_plan",
    "update_status_handler",
    "analysis_plan",
    "design_plan",
    "change_plan",
    "backlog_plan",
    "overview_plan",
]
