from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aware_environment.fs import apply_plan
from aware_environment.fs.receipt import Receipt, WriteOp
from aware_environments.kernel.objects.project.handlers import (
    create_task,
    create_task_handler,
    list_projects,
    project_status,
    project_tasks,
    task_index_refresh,
)
from aware_environments.kernel.objects.project.schemas import ProjectListEntry, ProjectTasksPayload
from aware_environments.kernel.objects.project.write_plan import CreateTaskPlanResult
from aware_environments.kernel.objects._shared.frontmatter import load_frontmatter


def _bootstrap_project(tmp_path: Path, slug: str = "demo-project") -> Path:
    projects_root = tmp_path / "docs" / "projects"
    project_path = projects_root / slug
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "OVERVIEW.md").write_text(
        """---
status: running
priority: medium
updated: "2025-10-10T00:00:00Z"
author:
  agent: "kernel-tests"
---
# Demo Project
""",
        encoding="utf-8",
    )
    return projects_root


def _apply_create_task(
    projects_root: Path,
    *,
    project_slug: str,
    task_slug: str,
    status: str = "running",
    backlog_entry: bool = False,
) -> CreateTaskPlanResult:
    result = create_task(
        projects_root,
        project_slug=project_slug,
        task_slug=task_slug,
        status=status,
        backlog_entry=backlog_entry,
        author={"agent": "kernel-tests", "process": "unit", "thread": "main"},
    )
    assert isinstance(result, CreateTaskPlanResult)
    receipt = apply_plan(result.plan)
    assert isinstance(receipt, Receipt)
    return result


def test_create_task_plan_writes_scaffold(tmp_path: Path) -> None:
    projects_root = _bootstrap_project(tmp_path)
    result = _apply_create_task(
        projects_root,
        project_slug="demo-project",
        task_slug="queued-task",
        status="queued",
        backlog_entry=True,
    )

    task_rel_path = result.task_payload["path"]
    assert task_rel_path.startswith("demo-project/tasks/_pending/queued-task")
    task_dir = projects_root / task_rel_path
    assert task_dir.is_dir()

    overview = load_frontmatter(task_dir / "OVERVIEW.md")
    assert overview.metadata["status"] == "queued"
    assert overview.metadata["priority"] == "medium"

    backlog_files = list((task_dir / "backlog").glob("*.md"))
    assert backlog_files, "Backlog entry should be created when backlog_entry=True."

    directories = set(result.directories)
    expected_dirs = {
        "demo-project/tasks/_pending/queued-task",
        "demo-project/tasks/_pending/queued-task/analysis",
        "demo-project/tasks/_pending/queued-task/design",
        "demo-project/tasks/_pending/queued-task/backlog",
    }
    assert expected_dirs <= directories


def test_task_index_refresh_generates_index(tmp_path: Path) -> None:
    projects_root = _bootstrap_project(tmp_path)
    _apply_create_task(projects_root, project_slug="demo-project", task_slug="alpha")
    _apply_create_task(projects_root, project_slug="demo-project", task_slug="beta", status="queued")

    result = task_index_refresh(projects_root, project_slug="demo-project")
    receipt = apply_plan(result.plan)
    assert isinstance(receipt, Receipt)
    writes = [op for op in receipt.fs_ops if isinstance(op, WriteOp)]
    assert writes, "Expected task index plan to write .index.json."

    index_path = projects_root / "demo-project" / "tasks" / ".index.json"
    assert index_path.exists()
    data = json.loads(index_path.read_text(encoding="utf-8"))
    slugs = {entry["slug"] for entry in data}
    assert slugs == {"alpha", "_pending/beta"}
    assert all(entry["metadata"]["storage_mode"] == "filesystem" for entry in data)


def test_project_status_and_tasks_payload(tmp_path: Path) -> None:
    projects_root = _bootstrap_project(tmp_path)
    _apply_create_task(projects_root, project_slug="demo-project", task_slug="alpha")
    _apply_create_task(projects_root, project_slug="demo-project", task_slug="beta", status="queued")

    status_payload = project_status(projects_root, identifier="demo-project")
    assert status_payload.slug == "demo-project"
    assert status_payload.task_count == 2
    assert status_payload.path == projects_root / "demo-project"
    assert status_payload.overview_path == projects_root / "demo-project" / "OVERVIEW.md"
    assert {task.slug for task in status_payload.tasks} == {"demo-project/alpha", "demo-project/_pending/beta"}

    tasks_payload = project_tasks(
        projects_root,
        identifier="demo-project",
        status_filter=["queued"],
    )
    assert isinstance(tasks_payload, ProjectTasksPayload)
    assert len(tasks_payload.tasks) == 1
    queued_task = tasks_payload.tasks[0]
    assert queued_task.slug.endswith("/beta")
    assert queued_task.status == "queued"
    assert queued_task.slug.endswith("_pending/beta")
    assert isinstance(queued_task.path, Path)


def test_list_projects_reports_summary(tmp_path: Path) -> None:
    projects_root = _bootstrap_project(tmp_path)
    _apply_create_task(projects_root, project_slug="demo-project", task_slug="alpha")

    entries = list_projects(projects_root)
    assert entries, "Expected at least one project."
    entry = entries[0]
    assert isinstance(entry, ProjectListEntry)
    assert entry.slug == "demo-project"
    assert entry.path == projects_root / "demo-project"
    assert entry.task_count == 1


def test_create_task_handler_flags(tmp_path: Path) -> None:
    projects_root = _bootstrap_project(tmp_path)

    # Baseline task to ensure project structure exists.
    _apply_create_task(projects_root, project_slug="demo-project", task_slug="alpha")

    # Create queued task without index refresh; author overrides should propagate.
    handler_result = create_task_handler(
        projects_root,
        project_slug="demo-project",
        task_slug="beta",
        title="Beta Task",
        queued=True,
        author_agent="agent-x",
        author_process="proc-x",
        author_thread="thread-x",
        no_index_refresh=True,
    )
    apply_plan(handler_result.plan)
    for extra in handler_result.plans:
        apply_plan(extra)

    beta_dir = projects_root / "demo-project" / "tasks" / "_pending" / "beta"
    overview = load_frontmatter(beta_dir / "OVERVIEW.md")
    assert overview.metadata["status"] == "queued"
    assert overview.metadata["author"] == {
        "agent": "agent-x",
        "process": "proc-x",
        "thread": "thread-x",
    }
    assert handler_result.index_payload is None
    index_path = projects_root / "demo-project" / "tasks" / ".index.json"
    assert not index_path.exists(), "no_index_refresh=True should skip index writes"

    # Default invocation should refresh index and include the new task entry.
    result = create_task_handler(
        projects_root,
        project_slug="demo-project",
        task_slug="gamma",
        title="Gamma Task",
        backlog_entry=False,
        author_agent="agent-y",
        author_process="proc-y",
        author_thread="thread-y",
    )
    apply_plan(result.plan)
    for extra_plan in result.plans:
        apply_plan(extra_plan)

    assert result.index_payload is not None
    assert index_path.exists()
    data = json.loads(index_path.read_text(encoding="utf-8"))
    slugs = {entry["slug"] for entry in data}
    assert "_pending/beta" in slugs, "Queued task should appear after refresh"


def test_task_index_refresh_all(tmp_path: Path) -> None:
    projects_root = _bootstrap_project(tmp_path, slug="project-a")
    _apply_create_task(projects_root, project_slug="project-a", task_slug="alpha")

    other_root = _bootstrap_project(tmp_path, slug="project-b")
    _apply_create_task(other_root, project_slug="project-b", task_slug="beta")

    projects_root = tmp_path / "docs" / "projects"
    result = task_index_refresh(projects_root, all=True)
    apply_plan(result.plan)
    for extra_plan in result.plans:
        apply_plan(extra_plan)

    assert len(result.projects) == 2
    paths = {entry["path"] for entry in result.projects}
    assert (projects_root / "project-a" / "tasks" / ".index.json").as_posix() in paths
    assert (projects_root / "project-b" / "tasks" / ".index.json").as_posix() in paths

    for slug in ("project-a", "project-b"):
        index_path = projects_root / slug / "tasks" / ".index.json"
        assert index_path.exists()
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        assert payload, "Index should contain task entries"
