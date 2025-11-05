"""Project object specification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments


PROJECT_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "list": (
        ArgumentSpec("projects_root", ("--projects-root",), help="Override docs/projects root."),
        ArgumentSpec("status", ("--status",), help="Filter by project status.", multiple=True),
    ),
    "status": (
        ArgumentSpec("projects_root", ("--projects-root",), help="Override docs/projects root."),
        ArgumentSpec("project_slug", (), help="Resolved project slug (internal)."),
        ArgumentSpec("identifier", ("--identifier",), help="Explicit project identifier (fallback when slug not resolved)."),
    ),
    "tasks": (
        ArgumentSpec("projects_root", ("--projects-root",), help="Override docs/projects root."),
        ArgumentSpec("status", ("--status",), help="Filter by task status.", multiple=True),
        ArgumentSpec("identifier", ("--identifier",), help="Explicit project identifier (fallback when slug not resolved)."),
        ArgumentSpec("project_slug", (), help="Resolved project slug (internal)."),
    ),
    "create-task": (
        ArgumentSpec("projects_root", ("--projects-root",), help="Override docs/projects root."),
        ArgumentSpec("task_slug", ("--task",), help="Task slug (lowercase, hyphen separated).", required=True),
        ArgumentSpec("title", ("--title",), help="Task title."),
        ArgumentSpec("status", ("--status",), help="Initial lifecycle status.", choices=("queued", "running")),
        ArgumentSpec("priority", ("--priority",), help="Initial priority level.", choices=("low", "medium", "high", "critical")),
        ArgumentSpec("author_agent", ("--author-agent",), help="Author agent id."),
        ArgumentSpec("author_process", ("--author-process",), help="Author process id."),
        ArgumentSpec("author_thread", ("--author-thread",), help="Author thread id."),
        ArgumentSpec("backlog_entry", ("--backlog-entry",), help="Append backlog entry noting task creation.", expects_value=False, default=False),
        ArgumentSpec("no_index_refresh", ("--no-index-refresh",), help="Skip tasks/.index.json refresh.", expects_value=False, default=False),
        ArgumentSpec("queued", ("--queued",), help="Shortcut for queued status when --status omitted.", expects_value=False, default=False),
    ),
    "task-index-refresh": (
        ArgumentSpec("projects_root", ("--projects-root",), help="Override docs/projects root."),
        ArgumentSpec("all", ("--all",), help="Refresh every project under the root.", expects_value=False, default=False),
        ArgumentSpec("identifier", ("--identifier",), help="Explicit project identifier (fallback when slug not resolved)."),
        ArgumentSpec("project_slug", (), help="Resolved project slug (internal)."),
    ),
}


def _argument_metadata(name: str) -> Sequence[Mapping[str, object]]:
    return serialize_arguments(PROJECT_ARGUMENTS.get(name, ()))


def build_project_spec() -> ObjectSpec:
    metadata = {"default_selectors": {"projects_root": "docs/projects"}}

    functions = (
        ObjectFunctionSpec(
            name="list",
            handler_factory="aware_environments.kernel.objects.project.handlers:list_projects",
            description="List projects under the configured root.",
            metadata={
                "rule_ids": ("02-task-01-lifecycle",),
                "arguments": _argument_metadata("list"),
            },
        ),
        ObjectFunctionSpec(
            name="status",
            handler_factory="aware_environments.kernel.objects.project.handlers:project_status",
            description="Show project overview metadata and task summaries.",
            metadata={
                "rule_ids": ("02-task-01-lifecycle",),
                "selectors": ("project_slug",),
                "pathspecs": {"reads": ["project-overview", "project-tasks-index"]},
                "arguments": _argument_metadata("status"),
            },
        ),
        ObjectFunctionSpec(
            name="tasks",
            handler_factory="aware_environments.kernel.objects.project.handlers:project_tasks",
            description="List tasks belonging to the project.",
            metadata={
                "rule_ids": ("02-task-01-lifecycle",),
                "pathspecs": {"reads": ["project-tasks-dir"]},
                "selectors": ("project_slug",),
                "arguments": _argument_metadata("tasks"),
            },
        ),
        ObjectFunctionSpec(
            name="create-task",
            handler_factory="aware_environments.kernel.objects.project.handlers:create_task_handler",
            description="Create a new task scaffold under the project lifecycle directories.",
            metadata={
                "rule_ids": ("02-task-01-lifecycle", "02-task-03-change-tracking"),
                "selectors": ("project_slug", "task_slug", "task_bucket"),
                "pathspecs": {
                    "creates": [
                        "project-dir",
                        "project-tasks-dir",
                        "task-dir",
                        "task-overview",
                        "task-analysis",
                        "task-design",
                        "task-implementation-changes",
                        "task-backlog",
                        "task-features",
                        "task-assets",
                    ],
                    "updates": ["project-tasks-index"],
                },
                "arguments": _argument_metadata("create-task"),
            },
        ),
        ObjectFunctionSpec(
            name="task-index-refresh",
            handler_factory="aware_environments.kernel.objects.project.handlers:task_index_refresh",
            description="Regenerate docs/projects/<project>/tasks/.index.json.",
            metadata={
                "rule_ids": ("02-task-01-lifecycle", "02-task-03-change-tracking"),
                "selectors": ("project_slug",),
                "pathspecs": {
                    "reads": ["project-tasks-index"],
                    "updates": ["project-tasks-index", "project-tasks-dir"],
                },
                "arguments": _argument_metadata("task-index-refresh"),
            },
        ),
    )

    pathspecs = (
        PathSpec(
            id="project-dir",
            layout_path=("docs", "projects", "{project_slug}"),
            instantiation_path=("{project_slug}",),
            visibility=Visibility.PUBLIC,
            description="Project directory containing lifecycle documents and tasks.",
            metadata={"selectors": ("project_slug",), "kind": "directory"},
        ),
        PathSpec(
            id="project-overview",
            layout_path=("docs", "projects", "{project_slug}", "OVERVIEW.md"),
            instantiation_path=("{project_slug}", "OVERVIEW.md"),
            visibility=Visibility.PUBLIC,
            description="Mutable OVERVIEW.md tracking project status.",
            metadata={"selectors": ("project_slug",)},
        ),
        PathSpec(
            id="project-tasks-dir",
            layout_path=("docs", "projects", "{project_slug}", "tasks"),
            instantiation_path=("{project_slug}", "tasks"),
            visibility=Visibility.PUBLIC,
            description="Container for project tasks.",
            metadata={"selectors": ("project_slug",), "kind": "directory"},
        ),
        PathSpec(
            id="project-tasks-index",
            layout_path=("docs", "projects", "{project_slug}", "tasks", ".index.json"),
            instantiation_path=("{project_slug}", "tasks", ".index.json"),
            visibility=Visibility.PUBLIC,
            description="Generated task index consumed by tooling.",
            metadata={"selectors": ("project_slug",)},
        ),
    )

    return ObjectSpec(
        type="project",
        description="Project metadata management.",
        metadata=metadata,
        functions=functions,
        pathspecs=pathspecs,
    )


PROJECT_OBJECT_SPEC = build_project_spec()

__all__ = ["PROJECT_OBJECT_SPEC", "PROJECT_ARGUMENTS"]
