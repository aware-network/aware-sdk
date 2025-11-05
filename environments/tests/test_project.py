import json
from pathlib import Path

from aware_environment.fs import apply_plan
from aware_environments.kernel.objects.project import handlers as project_handlers


def _seed_project(root: Path) -> Path:
    project_dir = root / "sample-project"
    (project_dir / "tasks").mkdir(parents=True, exist_ok=True)
    overview = (
        "---\n"
        "id: project-123\n"
        "title: Sample Project\n"
        "status: running\n"
        "priority: medium\n"
        "created: 2025-01-01T00:00:00Z\n"
        "updated: 2025-01-02T00:00:00Z\n"
        "---\n\n"
        "# Sample Project\n"
    )
    (project_dir / "OVERVIEW.md").write_text(overview, encoding="utf-8")
    task_dir = project_dir / "tasks" / "alpha-task"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_overview = (
        "---\n"
        "id: task-1\n"
        "title: Alpha Task\n"
        "status: running\n"
        "priority: high\n"
        "created: 2025-01-02T00:00:00Z\n"
        "updated: 2025-01-03T00:00:00Z\n"
        "---\n\n"
        "# Alpha Task\n"
    )
    (task_dir / "OVERVIEW.md").write_text(task_overview, encoding="utf-8")
    return project_dir


def test_project_status_and_tasks(tmp_path: Path) -> None:
    projects_root = tmp_path / "docs" / "projects"
    _seed_project(projects_root)
    all_projects = project_handlers.list_projects(projects_root)
    assert all_projects and all_projects[0].slug == "sample-project"

    status_payload = project_handlers.project_status(projects_root, identifier="sample-project")
    assert status_payload.title == "Sample Project"
    assert status_payload.task_count == 1

    tasks_payload = project_handlers.project_tasks(projects_root, identifier="sample-project")
    assert tasks_payload.project == "sample-project"
    assert len(tasks_payload.tasks) == 1
    assert tasks_payload.tasks[0].title == "Alpha Task"


def test_project_lookup_by_uuid(tmp_path: Path) -> None:
    projects_root = tmp_path / "docs" / "projects"
    project_dir = _seed_project(projects_root)
    status_payload = project_handlers.project_status(projects_root, identifier="project-123")
    assert status_payload.slug == "sample-project"

    # Ensure status filter works via list_projects
    entries = project_handlers.list_projects(projects_root, status_filter=["running"])
    assert entries and entries[0].slug == "sample-project"


def test_build_task_index(tmp_path: Path) -> None:
    projects_root = tmp_path / "docs" / "projects"
    _seed_project(projects_root)
    index = project_handlers.build_task_index(projects_root, project_slug="sample-project")
    assert len(index) == 1
    entry = index[0]
    assert entry.slug.endswith("alpha-task")
    assert entry.status == "running"
    assert entry.metadata["storage_mode"] == "filesystem"


def test_project_create_task_plan(tmp_path: Path) -> None:
    projects_root = tmp_path / "docs" / "projects"
    project_dir = _seed_project(projects_root)
    result = project_handlers.create_task(
        projects_root,
        project_slug="sample-project",
        task_slug="beta-task",
        title="Beta Task",
        backlog_entry=True,
    )

    apply_plan(result.plan)

    task_dir = project_dir / "tasks" / "beta-task"
    overview_path = task_dir / "OVERVIEW.md"
    assert overview_path.exists()
    content = overview_path.read_text(encoding="utf-8")
    assert "Beta Task" in content

    if result.backlog_path:
        backlog_target = projects_root / result.backlog_path
        assert backlog_target.exists()


def test_project_task_index_plan(tmp_path: Path) -> None:
    projects_root = tmp_path / "docs" / "projects"
    _seed_project(projects_root)
    result = project_handlers.task_index_refresh(
        projects_root,
        project_slug="sample-project",
    )

    apply_plan(result.plan)

    index_path = result.index_path
    assert index_path.exists()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(payload) == len(result.entries)
