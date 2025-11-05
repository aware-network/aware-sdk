from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from aware_environment.fs import OperationPlan, OperationWritePolicy, apply_plan
from aware_environments.kernel.objects._shared.frontmatter import load_frontmatter
from aware_environments.kernel.objects.task.handlers import (
    TaskStatusPlanResult,
    analysis_plan,
    backlog_plan,
    design_plan,
    list_tasks,
    update_status_handler,
    update_status_plan,
)
from aware_environments.kernel.objects.task.write_plan import TaskPlanResult, plan_task_overview
from aware_environments.kernel.objects.project.handlers import create_task


def _write_overview(path: Path, status: str = "running") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "---\n" f"status: {status}\n" "priority: medium\n" "---\n\n" "# Demo Task\n"
    path.write_text(text, encoding="utf-8")


def _create_task(
    projects_root: Path,
    *,
    project_slug: str,
    task_slug: str,
    status: str = "running",
) -> None:
    (projects_root / project_slug).mkdir(parents=True, exist_ok=True)
    result = create_task(
        projects_root,
        project_slug=project_slug,
        task_slug=task_slug,
        title=task_slug.replace("-", " ").title(),
        status=status,
        priority="medium",
        author={"agent": "tester", "process": "proc", "thread": "thread"},
        backlog_entry=False,
    )
    apply_plan(result.plan)


def test_update_status_plan(tmp_path):
    projects_root = tmp_path / "docs" / "projects"
    project_path = projects_root / "demo-project"
    task_path = project_path / "tasks" / "demo-task"

    _write_overview(task_path / "OVERVIEW.md")

    result = update_status_plan(
        projects_root,
        project_slug="demo-project",
        task_slug="demo-task",
        target_status="finished_succeeded",
        reason="Completed successfully",
        author={"agent": "agent-demo", "process": "main", "thread": "thread"},
    )

    assert isinstance(result, TaskStatusPlanResult)
    payload = result.payload
    assert payload.project == "demo-project"
    assert payload.task == "demo-task"
    assert payload.previous_status == "running"
    assert payload.new_status == "finished_succeeded"
    assert payload.to_path.endswith("demo-task")
    assert payload.overview_metadata["status"] == "finished_succeeded"
    assert "Completed successfully" in payload.overview_body
    assert payload.backlog is not None
    assert payload.backlog["summary"].startswith("Status updated")

    plan = result.plan
    assert isinstance(plan, OperationPlan)
    assert plan.context.function == "update-status"
    assert plan.moves, "expected directory move instruction"
    assert any(write.doc_type == "overview" for write in plan.writes)
    backlog_writes = [write for write in plan.writes if write.doc_type == "backlog"]
    assert backlog_writes, "expected backlog write instruction"
    assert backlog_writes[0].policy is OperationWritePolicy.APPEND_ENTRY


def test_update_status_handler_returns_result(tmp_path):
    projects_root = tmp_path / "projects"
    project_path = projects_root / "demo-project"
    task_path = project_path / "tasks" / "demo-task"

    _write_overview(task_path / "OVERVIEW.md")

    result = update_status_handler(
        projects_root,
        project_slug="demo-project",
        task_slug="demo-task",
        target_status="queued",
    )

    assert isinstance(result, TaskStatusPlanResult)
    payload = result.payload
    assert payload.project == "demo-project"
    assert payload.task == "demo-task"
    assert payload.previous_status == "running"
    assert payload.new_status == "queued"
    assert payload.move_required is True
    assert isinstance(result.plan, OperationPlan)


def test_update_status_plan_move_does_not_precreate_destination(tmp_path):
    projects_root = tmp_path / "projects"
    project_path = projects_root / "demo-project"
    task_path = project_path / "tasks" / "demo-task"
    _write_overview(task_path / "OVERVIEW.md")

    result = update_status_plan(
        projects_root,
        project_slug="demo-project",
        task_slug="demo-task",
        target_status="finished_succeeded",
    )

    target_dir = project_path / "tasks" / "_completed" / "demo-task"
    ensures = {ensure.path for ensure in result.plan.ensure_dirs}
    assert target_dir not in ensures
    assert target_dir.parent in ensures

    assert result.plan.moves, "expected move instruction for completion transition"
    move = result.plan.moves[0]
    assert move.dest == target_dir


def test_update_status_plan_same_bucket_keeps_ensure(tmp_path):
    projects_root = tmp_path / "projects"
    project_path = projects_root / "demo-project"
    task_path = project_path / "tasks" / "demo-task"
    _write_overview(task_path / "OVERVIEW.md")

    result = update_status_plan(
        projects_root,
        project_slug="demo-project",
        task_slug="demo-task",
        target_status="running",
        reason="Progress update without status change",
        force=True,
    )

    target_dir = project_path / "tasks" / "demo-task"
    ensures = {ensure.path for ensure in result.plan.ensure_dirs}
    assert target_dir in ensures
    assert result.plan.moves == ()


def test_analysis_plan_returns_operation_plan(tmp_path):
    projects_root = tmp_path / "docs" / "projects"
    task_dir = projects_root / "demo" / "tasks" / "demo-task"
    (task_dir / "analysis").mkdir(parents=True, exist_ok=True)
    (task_dir / "design").mkdir(parents=True, exist_ok=True)

    result = analysis_plan(
        projects_root,
        project_slug="demo",
        task_slug="demo-task",
        task_bucket="",
        title="Initial analysis",
        slug=None,
        summary="demo",
        content="# Notes\n",
        author={"agent": "tester", "process": "proc", "thread": "thread"},
    )

    assert isinstance(result, TaskPlanResult)
    plan = result.plan
    assert plan.context.function == "analysis"
    assert plan.writes, "expected write instructions"
    write = plan.writes[0]
    assert write.policy.value == "write_once"
    assert write.doc_type == "analysis"
    payload = result.payload
    assert payload["doc_type"] == "analysis"
    assert payload["project"] == "demo"
    assert payload["task"] == "demo-task"


def test_design_plan_version_hook(tmp_path: Path):
    projects_root = tmp_path / "root"
    task_dir = projects_root / "demo" / "tasks" / "demo-task" / "design"
    task_dir.mkdir(parents=True, exist_ok=True)

    result = design_plan(
        projects_root,
        project_slug="demo",
        task_slug="demo-task",
        task_bucket="",
        title="Design v1",
        slug=None,
        summary="demo",
        content="# Design\n",
        author={"agent": "tester", "process": "proc", "thread": "thread"},
        version_bump="minor",
    )

    assert isinstance(result, TaskPlanResult)
    write = result.plan.writes[0]
    assert write.doc_type == "design"
    assert write.hook_metadata.get("version_bump") == "minor"
    assert result.payload["doc_type"] == "design"
    assert result.payload["hook_metadata"]["version_bump"] == "minor"


def test_backlog_plan_appends_existing_file(tmp_path: Path):
    projects_root = tmp_path / "workspace"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backlog_path = projects_root / "demo" / "tasks" / "demo-task" / "backlog" / f"{today}.md"
    backlog_path.parent.mkdir(parents=True, exist_ok=True)
    backlog_path.write_text(
        f"---\nid: entry\nsummary: prev\n---\n\n[{today}T00:00:00Z]\nInitial entry\n",
        encoding="utf-8",
    )

    result = backlog_plan(
        projects_root,
        project_slug="demo",
        task_slug="demo-task",
        task_bucket="",
        title="Follow-up",
        slug=None,
        summary="update",
        content="Additional notes",
        author={"agent": "tester", "process": "proc", "thread": "thread"},
    )

    assert isinstance(result, TaskPlanResult)
    plan = result.plan
    assert not plan.writes, "existing backlog updates should produce patch instructions"
    assert len(plan.patches) == 1
    patch = plan.patches[0]
    assert patch.doc_type == "backlog"
    assert patch.policy is OperationWritePolicy.APPEND_ENTRY
    receipt = apply_plan(plan)
    assert any(getattr(op, "type", "") == "write" for op in receipt.fs_ops)
    text = backlog_path.read_text(encoding="utf-8")
    assert "Initial entry" in text
    assert "Additional notes" in text
    assert result.payload["event"] == "appended"


def test_overview_plan_existing_file_uses_patch(tmp_path: Path, monkeypatch) -> None:
    projects_root = tmp_path / "workspace"
    task_dir = projects_root / "demo" / "tasks" / "demo-task"
    overview_path = task_dir / "OVERVIEW.md"
    overview_path.parent.mkdir(parents=True, exist_ok=True)
    overview_path.write_text(
        "---\nid: overview\nsummary: Initial\n---\n\n## Status\n- Running\n",
        encoding="utf-8",
    )

    fixed_now = datetime(2025, 11, 5, 6, 45, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "aware_environments.kernel.objects.task.write_plan._iso_now",
        lambda: fixed_now,
    )

    result = plan_task_overview(
        projects_root,
        function_name="overview",
        project_slug="demo",
        task_slug="demo-task",
        title="Task Overview",
        slug=None,
        summary="Updated",
        content="## Status\n- Updated",
        author={"agent": "tester", "process": "proc", "thread": "thread"},
    )

    assert isinstance(result, TaskPlanResult)
    plan = result.plan
    assert not plan.writes
    assert len(plan.patches) == 1
    patch = plan.patches[0]
    assert patch.doc_type == "overview"
    assert patch.policy is OperationWritePolicy.MODIFIABLE
    receipt = apply_plan(plan)
    assert any(getattr(op, "type", "") == "write" for op in receipt.fs_ops)
    frontmatter = load_frontmatter(overview_path)
    assert "Updated" in frontmatter.body
    assert frontmatter.metadata["updated"].startswith("2025-11-05T06:45:00")


def test_list_tasks_filters(tmp_path: Path) -> None:
    projects_root = tmp_path / "docs" / "projects"
    _create_task(projects_root, project_slug="demo", task_slug="alpha")
    _create_task(projects_root, project_slug="demo", task_slug="beta", status="queued")
    _create_task(projects_root, project_slug="other", task_slug="gamma")

    payload = list_tasks(projects_root)
    assert payload.tasks, "Expected tasks to be listed."
    assert any(entry.project == "demo" for entry in payload.tasks)

    filtered = list_tasks(projects_root, project_filter=["demo"], status_filter=["running"])
    assert filtered.tasks, "Expected filtered tasks."
    assert all(entry.project == "demo" for entry in filtered.tasks)
    assert all(entry.status.lower() == "running" for entry in filtered.tasks)
