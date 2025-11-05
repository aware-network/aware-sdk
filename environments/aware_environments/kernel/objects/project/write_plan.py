"""OperationPlan builders for project task creation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

import yaml

from aware_environment.fs import (
    EnsureInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)

from .._shared.frontmatter import load_frontmatter
from .utils import (
    TASK_DIR_TEMPLATE,
    _default_task_overview,
    _normalize_priority,
    _normalize_status,
    _task_bucket,
    _task_directory,
)


def _render_document(metadata: Mapping[str, object], body: str) -> str:
    header = yaml.safe_dump(dict(metadata), sort_keys=False).strip()
    content = body.rstrip() + "\n" if body.strip() else ""
    return f"---\n{header}\n---\n\n{content}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class CreateTaskPlanResult:
    """Result of planning a project.create-task invocation."""

    plan: OperationPlan
    task_payload: Dict[str, object]
    directories: Sequence[str]
    backlog_path: Optional[str]
    selectors: Mapping[str, str]
    plans: Sequence[OperationPlan] = ()
    index_payload: Optional[Dict[str, object]] = None


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path.resolve())


def _prepare_overview_metadata(
    *,
    task_slug: str,
    title: str,
    status: str,
    priority: str,
    author: Mapping[str, str],
    timestamp: str,
) -> Dict[str, object]:
    return {
        "id": task_slug,
        "title": title,
        "slug": task_slug,
        "status": status,
        "priority": priority,
        "created": timestamp,
        "updated": timestamp,
        "author": dict(author),
    }


def _prepare_backlog_content(
    path: Path,
    *,
    task_slug: str,
    timestamp: datetime,
    author: Mapping[str, str],
    summary: Optional[str],
    entry_body: str,
) -> Dict[str, object]:
    stamp = timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    date_slug = timestamp.strftime("%Y-%m-%d")
    author_block = {
        "agent": author.get("agent", ""),
        "process": author.get("process", ""),
        "thread": author.get("thread", ""),
    }
    body_block = f"[{stamp}]\n{entry_body.rstrip()}\n"

    if path.exists():
        existing = load_frontmatter(path)
        metadata = dict(existing.metadata)
        metadata.setdefault("id", f"{task_slug}-backlog-{date_slug}")
        metadata.setdefault("title", f"{task_slug}-backlog-{date_slug}")
        metadata["slug"] = f"{task_slug}-backlog-{date_slug}"
        metadata["updated"] = stamp
        metadata["author"] = author_block
        metadata["summary"] = summary or metadata.get("summary", "")
        existing_body = existing.body.rstrip()
        combined_body = f"{existing_body}\n\n{body_block}" if existing_body else body_block
    else:
        metadata = {
            "id": f"{task_slug}-backlog-{date_slug}",
            "title": f"{task_slug}-backlog-{date_slug}",
            "slug": f"{task_slug}-backlog-{date_slug}",
            "created": stamp,
            "updated": stamp,
            "author": author_block,
            "summary": summary or "",
        }
        combined_body = body_block

    content = _render_document(metadata, combined_body)
    return {"metadata": metadata, "content": content, "event": "modified" if path.exists() else "created"}


def plan_create_task(
    projects_root: Path,
    *,
    project_slug: str,
    task_slug: str,
    title: Optional[str] = None,
    status: str = "running",
    priority: str = "medium",
    author: Optional[Mapping[str, str]] = None,
    backlog_entry: bool = False,
) -> CreateTaskPlanResult:
    projects_root = Path(projects_root).resolve()
    project_path = projects_root / project_slug
    if not project_path.exists():
        raise ValueError(f"Project '{project_slug}' not found under {projects_root}.")

    status_value = _normalize_status(status)
    priority_value = _normalize_priority(priority)
    bucket = _task_bucket(status_value)
    task_dir = _task_directory(project_path, task_slug, status_value)
    tasks_root = project_path / "tasks"

    if task_dir.exists():
        raise FileExistsError(f"Task '{task_slug}' already exists in project '{project_slug}'.")

    author_data = dict(author or {})
    author_data.setdefault("agent", "unknown")
    author_data.setdefault("process", "unknown")
    author_data.setdefault("thread", "unknown")

    title_value = (title or task_slug.replace("-", " ").title()).strip()
    now_dt = _now()
    iso_now = now_dt.isoformat().replace("+00:00", "Z")

    overview_metadata = _prepare_overview_metadata(
        task_slug=task_slug,
        title=title_value,
        status=status_value,
        priority=priority_value,
        author=author_data,
        timestamp=iso_now,
    )
    overview_body = _default_task_overview(title_value, status_value, author_data)
    overview_path = task_dir / "OVERVIEW.md"
    overview_event = "modified" if overview_path.exists() else "created"
    overview_content = _render_document(overview_metadata, overview_body)

    ensure_paths = {
        tasks_root,
        task_dir,
        *(task_dir / subpath for subpath in TASK_DIR_TEMPLATE.values()),
    }

    writes = [
        WriteInstruction(
            path=overview_path,
            content=overview_content,
            policy=OperationWritePolicy.MODIFIABLE,
            event=overview_event,
            doc_type="task-overview",
            timestamp=now_dt,
            metadata={
                "project": project_slug,
                "task": task_slug,
                "bucket": bucket,
            },
        )
    ]

    backlog_path_value: Optional[str] = None
    if backlog_entry:
        backlog_dir = task_dir / "backlog"
        ensure_paths.add(backlog_dir)
        backlog_target = backlog_dir / f"{now_dt.strftime('%Y-%m-%d')}.md"
        backlog_payload = _prepare_backlog_content(
            backlog_target,
            task_slug=task_slug,
            timestamp=now_dt,
            author=author_data,
            summary=f"Task created with status {status_value}.",
            entry_body="- Task scaffold created via `project.create-task`.",
        )
        writes.append(
            WriteInstruction(
                path=backlog_target,
                content=backlog_payload["content"],
                policy=OperationWritePolicy.MODIFIABLE,
                event=backlog_payload["event"],
                doc_type="task-backlog",
                timestamp=now_dt,
                metadata={
                    "project": project_slug,
                    "task": task_slug,
                    "bucket": bucket,
                },
            )
        )
        backlog_path_value = _relative(backlog_target, projects_root)

    ensure_instructions = tuple(
        EnsureInstruction(path=path) for path in sorted(ensure_paths, key=lambda value: value.as_posix())
    )

    selectors = {
        "project_slug": project_slug,
        "task_slug": task_slug,
        "task_bucket": bucket,
    }
    context = OperationContext(
        object_type="project",
        function="create-task",
        selectors=selectors,
    )

    plan = OperationPlan(
        context=context,
        ensure_dirs=ensure_instructions,
        writes=tuple(writes),
    )

    directories = [_relative(task_dir, projects_root)]
    for key, template in TASK_DIR_TEMPLATE.items():
        directories.append(_relative(task_dir / template, projects_root))

    task_payload = {
        "slug": task_slug,
        "title": title_value,
        "status": status_value,
        "priority": priority_value,
        "path": _relative(task_dir, projects_root),
        "overview_path": _relative(overview_path, projects_root),
        "created_at": iso_now,
    }

    return CreateTaskPlanResult(
        plan=plan,
        task_payload=task_payload,
        directories=tuple(dict.fromkeys(directories)),
        backlog_path=backlog_path_value,
        selectors=selectors,
    )


__all__ = ["CreateTaskPlanResult", "plan_create_task"]
