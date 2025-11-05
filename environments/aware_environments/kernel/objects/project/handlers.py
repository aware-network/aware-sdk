"""Kernel handlers for project metadata operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import UUID, uuid5

from aware_environment.fs import (
    EnsureInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)

from .._shared.frontmatter import load_frontmatter, FrontmatterResult
from .._shared.timeline import ensure_aware_datetime
from ..repository.fs import RepositoryFSAdapter
from .utils import (
    TASK_DIR_TEMPLATE,
    _default_task_overview,
    _normalize_priority,
    _normalize_status,
    _task_bucket,
    _task_directory,
)
from .schemas import (
    ProjectListEntry,
    ProjectStatusPayload,
    ProjectTaskIndexEntry,
    ProjectTaskPath,
    ProjectTaskSummary,
    ProjectTasksPayload,
)
from .write_plan import CreateTaskPlanResult, plan_create_task


@dataclass
class TaskSummary:
    slug: str
    path: Path
    metadata: Dict[str, object]
    title: str
    status: str
    priority: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@dataclass
class ProjectSummary:
    slug: str
    path: Path
    metadata: Dict[str, object]
    title: str
    status: str
    priority: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    last_modified: Optional[datetime]
    tasks: List[TaskSummary]

@dataclass(frozen=True)
class TaskIndexPlanResult:
    plan: OperationPlan
    entries: Tuple[ProjectTaskIndexEntry, ...]
    index_path: Path
    plans: Tuple[OperationPlan, ...] = ()
    projects: Tuple[Dict[str, object], ...] = ()


# Namespace used in CLI for deterministic task ids
TASK_ID_NAMESPACE = UUID("0fb34269-9a43-4fc4-a400-5ac0d951c1b7")


# ---------------------------------------------------------------------------
# Project + task discovery helpers
# ---------------------------------------------------------------------------


def _coerce_projects_root(projects_root: Path | str | None) -> Path:
    base = Path(projects_root or "docs/projects")
    return base.resolve() if not base.is_absolute() else base


def _iter_project_directories(projects_root: Path) -> Iterable[Tuple[str, Path]]:
    if not projects_root.exists():
        return []

    directories: List[Tuple[str, Path]] = []
    for child in sorted(projects_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_"):
            for nested in sorted(child.iterdir()):
                if nested.is_dir():
                    slug = f"{child.name}/{nested.name}"
                    directories.append((slug, nested))
            continue
        directories.append((child.name, child))
    return directories


def _iter_task_directories(tasks_root: Path) -> Iterable[Tuple[str, Path]]:
    if not tasks_root.exists():
        return []
    directories: List[Tuple[str, Path]] = []
    for child in sorted(tasks_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_"):
            for nested in sorted(child.iterdir()):
                if nested.is_dir():
                    slug = f"{child.name}/{nested.name}"
                    directories.append((slug, nested))
            continue
        directories.append((child.name, child))
    return directories


def _bucket_for_slug(slug: str) -> str:
    if slug.startswith("_pending/"):
        return "_pending"
    if slug.startswith("_completed/"):
        return "_completed"
    return ""


def _infer_status(bucket: str, metadata: Dict[str, object]) -> str:
    status = metadata.get("status")
    if isinstance(status, str) and status.strip():
        return status.strip()
    if bucket == "_pending":
        return "queued"
    if bucket == "_completed":
        return "completed"
    return "running"


def _infer_priority(metadata: Dict[str, object]) -> str:
    value = metadata.get("priority")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "medium"


def _load_task_summary(project_slug: str, slug: str, path: Path) -> TaskSummary:
    overview_path = path / "OVERVIEW.md"
    if overview_path.exists():
        fm = load_frontmatter(overview_path)
    else:
        fm = FrontmatterResult(metadata={}, body="")
    metadata = dict(fm.metadata)
    bucket = _bucket_for_slug(slug)
    status = _infer_status(bucket, metadata)
    priority = _infer_priority(metadata)
    title = str(metadata.get("title") or path.name.replace("-", " ").title())
    created = ensure_aware_datetime(metadata.get("created"))
    updated = ensure_aware_datetime(metadata.get("updated"))
    return TaskSummary(
        slug=slug,
        path=path,
        metadata=metadata,
        title=title,
        status=status,
        priority=priority,
        created_at=created,
        updated_at=updated,
    )


def _load_project_summary(projects_root: Path, slug: str, path: Path) -> ProjectSummary:
    overview_path = path / "OVERVIEW.md"
    if overview_path.exists():
        fm = load_frontmatter(overview_path)
    else:
        fm = FrontmatterResult(metadata={}, body="")
    metadata = dict(fm.metadata)
    title = str(metadata.get("title") or path.name.replace("-", " ").title())
    status = str(metadata.get("status") or metadata.get("project_status") or "running")
    priority = str(metadata.get("priority") or metadata.get("priority_level") or "medium")
    created = ensure_aware_datetime(metadata.get("created"))
    updated = ensure_aware_datetime(metadata.get("updated"))

    tasks_root = path / "tasks"
    tasks: List[TaskSummary] = []
    for task_slug, task_path in _iter_task_directories(tasks_root):
        tasks.append(_load_task_summary(slug, task_slug, task_path))

    last_modified_candidates: List[datetime] = []
    if updated:
        last_modified_candidates.append(updated)
    for task in tasks:
        if task.updated_at:
            last_modified_candidates.append(task.updated_at)
    last_modified = max(last_modified_candidates) if last_modified_candidates else None

    return ProjectSummary(
        slug=slug,
        path=path,
        metadata=metadata,
        title=title,
        status=status,
        priority=priority,
        created_at=created,
        updated_at=updated,
        last_modified=last_modified,
        tasks=tasks,
    )


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _task_payload(project_slug: str, task: TaskSummary) -> ProjectTaskSummary:
    raw_id = task.metadata.get("id")
    task_uuid = str(raw_id) if isinstance(raw_id, str) and raw_id.strip() else None
    return ProjectTaskSummary(
        id=task_uuid or f"{project_slug}/{task.slug}",
        uuid=task_uuid,
        slug=f"{project_slug}/{task.slug}",
        title=task.title,
        status=task.status,
        priority=task.priority,
        created_at=_iso(task.created_at),
        updated_at=_iso(task.updated_at),
        path=task.path,
    )


def _project_payload(summary: ProjectSummary) -> ProjectStatusPayload:
    raw_id = summary.metadata.get("id")
    project_uuid = str(raw_id) if isinstance(raw_id, str) and raw_id.strip() else None
    tasks_payload = [_task_payload(summary.slug, task) for task in summary.tasks]
    return ProjectStatusPayload(
        id=project_uuid or summary.slug,
        uuid=project_uuid,
        slug=summary.slug,
        title=summary.title,
        status=summary.status.lower() if isinstance(summary.status, str) else summary.status,
        priority=summary.priority,
        description=summary.metadata.get("description"),
        created_at=_iso(summary.created_at),
        updated_at=_iso(summary.updated_at),
        last_modified=_iso(summary.last_modified),
        task_count=len(summary.tasks),
        tasks=tasks_payload,
        metadata=dict(summary.metadata),
        path=summary.path,
        overview_path=summary.path / "OVERVIEW.md",
    )


# Task index helpers ---------------------------------------------------------


def _generate_task_id(project_slug: str, task_slug: str) -> str:
    slug = f"{project_slug}/{task_slug}"
    return str(uuid5(TASK_ID_NAMESPACE, slug))


def _resolve_repository_context(projects_root: Path, project_path: Path) -> Tuple[str, str, Path]:
    """Resolve repository id and root path for the project."""
    try:
        repo_root = project_path.parents[2]
    except IndexError:
        repo_root = projects_root

    adapter = RepositoryFSAdapter(repo_root)
    entries = adapter.read_index()
    resolved_root = repo_root.resolve()

    for entry in entries:
        workspace_root = entry.workspace_root if hasattr(entry, "workspace_root") else entry.get("workspace_root")
        if not isinstance(workspace_root, str):
            continue
        try:
            workspace_path = Path(workspace_root).resolve()
        except OSError:
            continue
        if workspace_path == resolved_root:
            repository_id = entry.repository_id if hasattr(entry, "repository_id") else entry.get("repository_id", "")
            repo_root_path = entry.metadata.get("repository_root_path", ".") if hasattr(entry, "metadata") else entry.get("repository_root_path", ".")
            return str(repository_id), str(repo_root_path or "."), repo_root

    repository_id = sha256(str(resolved_root).encode("utf-8")).hexdigest()
    return repository_id, ".", repo_root


def _compute_task_hash(task_path: Path) -> str:
    digest = sha256()
    if not task_path.exists():
        return digest.hexdigest()
    files = sorted(path for path in task_path.rglob("*") if path.is_file())
    for file_path in files:
        rel = file_path.relative_to(task_path).as_posix()
        stat = file_path.stat()
        digest.update(rel.encode("utf-8"))
        digest.update(str(stat.st_size).encode("utf-8"))
        digest.update(str(int(stat.st_mtime_ns)).encode("utf-8"))
    return digest.hexdigest()


def _build_paths_payload(task_path: Path, directories: Dict[str, str], manifest_path: Optional[str]) -> List[Dict[str, object]]:
    mapping = [
        ("task_root", "task-root", True),
        ("overview", "overview", False),
        ("analysis", "analysis", False),
        ("design", "design", False),
        ("backlog", "backlog", False),
        ("implementation_changes", "implementation-changes", False),
    ]
    payload: List[Dict[str, object]] = []
    for key, label, is_root in mapping:
        path_value = directories.get(key)
        if path_value:
            payload.append(
                {
                    "key": label,
                    "path": path_value,
                    "is_root": is_root,
                }
            )
    if manifest_path:
        payload.append(
            {
                "key": "manifest",
                "path": manifest_path,
                "is_root": False,
            }
        )
    return payload


def _rel_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return path.resolve().as_posix()


def _task_index_entry(
    project_slug: str,
    task: TaskSummary,
    project_path: Path,
    repository_id: str,
    repository_root_path: str,
    repo_root: Path,
) -> ProjectTaskIndexEntry:
    task_path = task.path
    task_root_rel = _rel_path(task_path, repo_root)

    directories = {"task_root": task_root_rel}
    path_candidates = {
        "overview": task_path / "OVERVIEW.md",
        "analysis": task_path / "analysis",
        "design": task_path / "design",
        "backlog": task_path / "backlog",
        "implementation_changes": task_path / "implementation" / "changes",
    }

    for name, candidate in path_candidates.items():
        if candidate.exists():
            directories[name] = _rel_path(candidate, repo_root)

    manifest_path = directories.get("overview")
    task_id = task.metadata.get("id") or _generate_task_id(project_slug, task.slug)
    slug = task.slug

    metadata = dict(task.metadata)
    metadata.setdefault("storage_mode", "filesystem")

    path_entries = [ProjectTaskPath(**entry) for entry in _build_paths_payload(task_path, directories, manifest_path)]
    timestamp = datetime.now(timezone.utc)
    return ProjectTaskIndexEntry(
        task_id=task_id,
        slug=slug,
        status=task.status,
        task_root=directories["task_root"],
        manifest_path=manifest_path,
        directories=directories,
        repository_id=repository_id,
        repository_root_path=repository_root_path,
        paths=path_entries,
        hash=_compute_task_hash(task_path),
        metadata=metadata,
        updated_at=timestamp,
    )


# ---------------------------------------------------------------------------
# Kernel handlers exposed via ObjectSpec
# ---------------------------------------------------------------------------


def _load_all_projects(projects_root: Path) -> List[ProjectSummary]:
    summaries: List[ProjectSummary] = []
    for slug, path in _iter_project_directories(projects_root):
        summaries.append(_load_project_summary(projects_root, slug, path))
    return summaries


def list_projects(
    projects_root: Path | str | None,
    *,
    status: Optional[Sequence[str]] = None,
    status_filter: Optional[Sequence[str]] = None,
) -> List[ProjectListEntry]:
    projects_root = _coerce_projects_root(projects_root)
    status_values = status_filter if status_filter is not None else status
    status_filter_set = {value.lower() for value in status_values or []}
    entries: List[ProjectListEntry] = []
    for summary in _load_all_projects(projects_root):
        if status_filter_set and summary.status.lower() not in status_filter_set:
            continue
        entry = ProjectListEntry(
            id=summary.metadata.get("id") or summary.slug,
            uuid=summary.metadata.get("id"),
            slug=summary.slug,
            title=summary.title,
            status=summary.status.lower() if isinstance(summary.status, str) else summary.status,
            priority=summary.priority,
            task_count=len(summary.tasks),
            last_modified=_iso(summary.last_modified),
            path=summary.path,
        )
        entries.append(entry)
    return entries


def _resolve_project(
    projects_root: Path,
    identifier: str,
) -> ProjectSummary:
    summaries = _load_all_projects(projects_root)
    for summary in summaries:
        if summary.slug == identifier:
            return summary
    for summary in summaries:
        raw_id = summary.metadata.get("id")
        if raw_id and str(raw_id) == identifier:
            return summary
    raise ValueError(f"Project '{identifier}' not found under {projects_root}")


def _resolve_identifier(
    *,
    project_slug: Optional[str],
    identifier: Optional[str],
) -> str:
    if project_slug:
        return project_slug
    if identifier:
        return identifier
    raise ValueError("Project identifier required (project_slug or identifier).")


def project_status(
    projects_root: Path | str | None,
    *,
    project_slug: Optional[str] = None,
    identifier: Optional[str] = None,
) -> ProjectStatusPayload:
    projects_root = _coerce_projects_root(projects_root)
    summary = _resolve_project(projects_root, _resolve_identifier(project_slug=project_slug, identifier=identifier))
    return _project_payload(summary)


def project_tasks(
    projects_root: Path | str | None,
    *,
    project_slug: Optional[str] = None,
    identifier: Optional[str] = None,
    status_filter: Optional[Sequence[str]] = None,
    status: Optional[Sequence[str]] = None,
) -> ProjectTasksPayload:
    projects_root = _coerce_projects_root(projects_root)
    summary = _resolve_project(projects_root, _resolve_identifier(project_slug=project_slug, identifier=identifier))
    filter_values = status_filter if status_filter is not None else status
    filter_set = {value.lower() for value in filter_values or []}
    tasks = [task for task in summary.tasks if not filter_set or task.status.lower() in filter_set]
    return ProjectTasksPayload(
        project=summary.slug,
        tasks=[_task_payload(summary.slug, task) for task in tasks],
    )


def build_task_index(
    projects_root: Path,
    *,
    project_slug: str,
) -> List[ProjectTaskIndexEntry]:
    summary = _resolve_project(projects_root, project_slug)
    repository_id, repository_root_path, repo_root = _resolve_repository_context(projects_root, summary.path)
    entries: List[ProjectTaskIndexEntry] = []
    for task in summary.tasks:
        entries.append(
            _task_index_entry(summary.slug, task, summary.path, repository_id, repository_root_path, repo_root)
        )
    return entries


def _build_task_index_plan(
    projects_root: Path | str,
    summary: ProjectSummary,
) -> TaskIndexPlanResult:
    projects_root_path = _coerce_projects_root(projects_root)
    entries = build_task_index(projects_root_path, project_slug=summary.slug)
    project_path = projects_root_path / summary.slug
    index_path = project_path / "tasks" / ".index.json"
    tasks_dir = index_path.parent

    context = OperationContext(
        object_type="project",
        function="task-index-refresh",
        selectors={"project_slug": summary.slug},
    )
    timestamp = datetime.now(timezone.utc)
    event = "modified" if index_path.exists() else "created"
    entry_dicts = [entry.model_dump(mode="json") for entry in entries]
    payload = json.dumps(entry_dicts, indent=2) + "\n"

    plan = OperationPlan(
        context=context,
        ensure_dirs=(EnsureInstruction(path=tasks_dir),),
        writes=(
            WriteInstruction(
                path=index_path,
                content=payload,
                policy=OperationWritePolicy.MODIFIABLE,
                event=event,
                doc_type="project-task-index",
                timestamp=timestamp,
                metadata={
                    "project": summary.slug,
                    "count": len(entries),
                },
            ),
        ),
    )

    project_payload = {
        "project": summary.slug,
        "count": len(entries),
        "path": str(index_path),
        "entries": entry_dicts,
    }

    return TaskIndexPlanResult(
        plan=plan,
        entries=tuple(entries),
        index_path=index_path,
        projects=(project_payload,),
    )


def task_index_refresh(
    projects_root: Path | str | None,
    *,
    project_slug: Optional[str] = None,
    identifier: Optional[str] = None,
    all: bool = False,
) -> TaskIndexPlanResult:
    projects_root_path = _coerce_projects_root(projects_root)
    summaries = _load_all_projects(projects_root_path)

    if all:
        results = [_build_task_index_plan(projects_root_path, summary) for summary in summaries]
        if not results:
            raise ValueError(f"No projects found under {projects_root}.")

        first = results[0]
        additional_plans: List[OperationPlan] = list(first.plans)
        project_payloads: List[Dict[str, object]] = [payload for payload in first.projects]
        for result in results[1:]:
            additional_plans.append(result.plan)
            additional_plans.extend(result.plans)
            project_payloads.extend(result.projects)

        aggregated_entries: List[ProjectTaskIndexEntry] = []
        for result in results:
            aggregated_entries.extend(result.entries)

        return TaskIndexPlanResult(
            plan=first.plan,
            plans=tuple(additional_plans),
            entries=tuple(aggregated_entries),
            index_path=first.index_path,
            projects=tuple(project_payloads),
        )

    target_slug = _resolve_identifier(project_slug=project_slug, identifier=identifier)
    summary = next((candidate for candidate in summaries if candidate.slug == target_slug), None)
    if summary is None:
        raise ValueError(f"Project '{target_slug}' not found under {projects_root_path}.")

    return _build_task_index_plan(projects_root_path, summary)


def create_task(
    projects_root: Path,
    *,
    project_slug: str,
    task_slug: str,
    title: Optional[str] = None,
    status: str = "running",
    priority: str = "medium",
    author: Optional[Dict[str, str]] = None,
    backlog_entry: bool = False,
) -> CreateTaskPlanResult:
    return plan_create_task(
        projects_root,
        project_slug=project_slug,
        task_slug=task_slug,
        title=title,
        status=status,
        priority=priority,
        author=author,
        backlog_entry=backlog_entry,
    )


def _build_author_map(
    *,
    author: Optional[Dict[str, str]],
    author_agent: Optional[str],
    author_process: Optional[str],
    author_thread: Optional[str],
) -> Dict[str, str]:
    data = dict(author or {})
    if author_agent:
        data["agent"] = author_agent
    if author_process:
        data["process"] = author_process
    if author_thread:
        data["thread"] = author_thread
    data.setdefault("agent", "Codex")
    data.setdefault("process", "fs-tooling")
    data.setdefault("thread", "fs-tooling-summary-cli")
    return data


def create_task_handler(
    projects_root: Path | str | None,
    *,
    project_slug: str,
    task_slug: str,
    title: Optional[str] = None,
    status: str = "running",
    queued: bool = False,
    priority: str = "medium",
    author: Optional[Dict[str, str]] = None,
    author_agent: Optional[str] = None,
    author_process: Optional[str] = None,
    author_thread: Optional[str] = None,
    backlog_entry: bool = False,
    no_index_refresh: bool = False,
) -> CreateTaskPlanResult:
    projects_root_path = _coerce_projects_root(projects_root)
    status_value = "queued" if queued and (not status or status.lower() == "running") else status
    author_map = _build_author_map(
        author=author,
        author_agent=author_agent,
        author_process=author_process,
        author_thread=author_thread,
    )

    create_result = create_task(
        projects_root_path,
        project_slug=project_slug,
        task_slug=task_slug,
        title=title,
        status=status_value,
        priority=priority,
        author=author_map,
        backlog_entry=backlog_entry,
    )

    extra_plans: List[OperationPlan] = []
    index_payload: Optional[Dict[str, object]] = None
    if not no_index_refresh:
        index_result = task_index_refresh(
            projects_root_path,
            project_slug=project_slug,
        )
        extra_plans.append(index_result.plan)
        extra_plans.extend(index_result.plans)
        if index_result.projects:
            index_payload = dict(index_result.projects[0])
        else:
            index_payload = {
                "project": project_slug,
                "count": len(index_result.entries),
                "path": str(index_result.index_path),
                "entries": [entry.model_dump(mode="json") for entry in index_result.entries],
            }

    return CreateTaskPlanResult(
        plan=create_result.plan,
        task_payload=create_result.task_payload,
        directories=create_result.directories,
        backlog_path=create_result.backlog_path,
        selectors=create_result.selectors,
        plans=tuple(extra_plans),
        index_payload=index_payload,
    )


__all__ = [
    "list_projects",
    "project_status",
    "project_tasks",
    "build_task_index",
    "task_index_refresh",
    "CreateTaskPlanResult",
    "create_task",
    "create_task_handler",
    "TaskIndexPlanResult",
]
