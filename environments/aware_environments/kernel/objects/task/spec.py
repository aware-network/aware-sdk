"""Task object specification."""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments


TASK_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "list": (
        ArgumentSpec("projects_root", ("--projects-root",), help="Override docs/projects root."),
        ArgumentSpec("project_filter", ("--project",), help="Filter by project slug.", multiple=True),
        ArgumentSpec("status_filter", ("--status",), help="Filter by task status.", multiple=True),
    ),
    "analysis": (
        ArgumentSpec("projects_root", ()),
        ArgumentSpec("project_slug", ()),
        ArgumentSpec("task_slug", ()),
        ArgumentSpec("author", ()),
        ArgumentSpec("title", ("--title",), help="Document title.", required=True),
        ArgumentSpec("summary", ("--summary",), help="Short summary."),
        ArgumentSpec("content", ("--content",), help="Inline markdown content."),
        ArgumentSpec("content_file", ("--content-file",), help="Path to markdown content."),
        ArgumentSpec("slug", ("--slug",), help="Optional document slug."),
    ),
    "design": (
        ArgumentSpec("projects_root", ()),
        ArgumentSpec("project_slug", ()),
        ArgumentSpec("task_slug", ()),
        ArgumentSpec("author", ()),
        ArgumentSpec("title", ("--title",), help="Document title.", required=True),
        ArgumentSpec("summary", ("--summary",), help="Short summary."),
        ArgumentSpec("content", ("--content",), help="Inline markdown content."),
        ArgumentSpec("content_file", ("--content-file",), help="Path to markdown content."),
        ArgumentSpec("slug", ("--slug",), help="Optional document slug."),
        ArgumentSpec("version_bump", ("--version-bump",), help="Design version increment (major|minor|patch|none)."),
    ),
    "change": (
        ArgumentSpec("projects_root", ()),
        ArgumentSpec("project_slug", ()),
        ArgumentSpec("task_slug", ()),
        ArgumentSpec("author", ()),
        ArgumentSpec("title", ("--title",), help="Change entry title.", required=True),
        ArgumentSpec("summary", ("--summary",), help="Short summary."),
        ArgumentSpec("content", ("--content",), help="Inline markdown content."),
        ArgumentSpec("content_file", ("--content-file",), help="Path to markdown content."),
        ArgumentSpec("slug", ("--slug",), help="Optional document slug."),
    ),
    "overview": (
        ArgumentSpec("projects_root", ()),
        ArgumentSpec("project_slug", ()),
        ArgumentSpec("task_slug", ()),
        ArgumentSpec("author", ()),
        ArgumentSpec("title", ("--title",), help="Overview title.", required=True),
        ArgumentSpec("summary", ("--summary",), help="Overview summary."),
        ArgumentSpec("content", ("--content",), help="Inline markdown content."),
        ArgumentSpec("content_file", ("--content-file",), help="Path to markdown content."),
        ArgumentSpec("slug", ("--slug",), help="Optional document slug."),
    ),
    "backlog": (
        ArgumentSpec("projects_root", ()),
        ArgumentSpec("project_slug", ()),
        ArgumentSpec("task_slug", ()),
        ArgumentSpec("author", ()),
        ArgumentSpec("title", ("--title",), help="Backlog entry title.", required=True),
        ArgumentSpec("summary", ("--summary",), help="Short summary."),
        ArgumentSpec("content", ("--content",), help="Inline markdown content."),
        ArgumentSpec("content_file", ("--content-file",), help="Path to markdown content."),
        ArgumentSpec("slug", ("--slug",), help="Optional document slug."),
    ),
    "update-status": (
        ArgumentSpec("projects_root", ()),
        ArgumentSpec("project_slug", ()),
        ArgumentSpec("task_slug", ()),
        ArgumentSpec("author", ()),
        ArgumentSpec(
            "target_status",
            ("--status",),
            help="New task status.",
            required=True,
        ),
        ArgumentSpec("reason", ("--reason",), help="Reason for status change (logged to backlog)."),
        ArgumentSpec("force", ("--force",), help="Force update even if status unchanged.", expects_value=False),
    ),
}


def _argument_metadata(name: str) -> Sequence[Mapping[str, object]]:
    return serialize_arguments(TASK_ARGUMENTS.get(name, ()))


def build_task_spec() -> ObjectSpec:
    metadata = {"default_selectors": {"projects_root": "docs/projects"}}

    functions = (
        ObjectFunctionSpec(
            name="list",
            handler_factory="aware_environments.kernel.objects.task.handlers:list_tasks",
            metadata={
                "rule_ids": ("02-task-01-lifecycle",),
                "arguments": _argument_metadata("list"),
            },
        ),
        ObjectFunctionSpec(
            name="analysis",
            handler_factory="aware_environments.kernel.objects.task.handlers:analysis_plan",
            metadata={
                "rule_ids": ("02-task-01-lifecycle",),
                "selectors": ("project_slug", "task_slug", "task_bucket"),
                "pathspecs": {"updates": ["task-analysis"]},
                "arguments": _argument_metadata("analysis"),
            },
        ),
        ObjectFunctionSpec(
            name="design",
            handler_factory="aware_environments.kernel.objects.task.handlers:design_plan",
            metadata={
                "rule_ids": ("02-task-01-lifecycle",),
                "selectors": ("project_slug", "task_slug", "task_bucket"),
                "pathspecs": {"updates": ["task-design"]},
                "arguments": _argument_metadata("design"),
            },
        ),
        ObjectFunctionSpec(
            name="change",
            handler_factory="aware_environments.kernel.objects.task.handlers:change_plan",
            metadata={
                "rule_ids": ("02-task-03-change-tracking",),
                "selectors": ("project_slug", "task_slug", "task_bucket"),
                "pathspecs": {"updates": ["task-implementation-changes"]},
                "arguments": _argument_metadata("change"),
            },
        ),
        ObjectFunctionSpec(
            name="overview",
            handler_factory="aware_environments.kernel.objects.task.handlers:overview_plan",
            metadata={
                "rule_ids": ("02-task-01-lifecycle",),
                "selectors": ("project_slug", "task_slug", "task_bucket"),
                "pathspecs": {"updates": ["task-overview"]},
                "arguments": _argument_metadata("overview"),
            },
        ),
        ObjectFunctionSpec(
            name="backlog",
            handler_factory="aware_environments.kernel.objects.task.handlers:backlog_plan",
            metadata={
                "rule_ids": ("02-task-01-lifecycle", "02-task-03-change-tracking"),
                "selectors": ("project_slug", "task_slug", "task_bucket"),
                "pathspecs": {"updates": ["task-backlog"]},
                "arguments": _argument_metadata("backlog"),
            },
        ),
        ObjectFunctionSpec(name="index-refresh"),
        ObjectFunctionSpec(
            name="update-status",
            handler_factory="aware_environments.kernel.objects.task.handlers:update_status_handler",
            description="Return the canonical plan for updating a task's lifecycle status.",
            metadata={
                "rule_ids": (
                    "02-task-01-lifecycle",
                    "02-task-02-status",
                    "02-task-03-change-tracking",
                ),
                "selectors": ("project_slug", "task_slug", "task_bucket"),
                "pathspecs": {
                    "reads": ["task-dir"],
                    "updates": ["task-dir", "task-overview", "task-backlog"],
                },
                "arguments": _argument_metadata("update-status"),
            },
        ),
    )

    pathspecs = (
        PathSpec(
            id="task-dir",
            layout_path=("docs", "projects", "{project_slug}", "tasks", "{task_bucket}", "{task_slug}"),
            instantiation_path=("{project_slug}", "tasks", "{task_bucket}", "{task_slug}"),
            visibility=Visibility.PUBLIC,
            description="Primary task directory (status-aware).",
            metadata={"selectors": ("project_slug", "task_slug", "task_bucket"), "kind": "directory"},
        ),
        PathSpec(
            id="task-overview",
            layout_path=("docs", "projects", "{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "OVERVIEW.md"),
            instantiation_path=("{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "OVERVIEW.md"),
            visibility=Visibility.PUBLIC,
            description="Task overview document path.",
            metadata={"selectors": ("project_slug", "task_slug", "task_bucket")},
        ),
        PathSpec(
            id="task-analysis",
            layout_path=("docs", "projects", "{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "analysis"),
            instantiation_path=("{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "analysis"),
            visibility=Visibility.PUBLIC,
            metadata={"selectors": ("project_slug", "task_slug", "task_bucket"), "kind": "directory"},
        ),
        PathSpec(
            id="task-design",
            layout_path=("docs", "projects", "{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "design"),
            instantiation_path=("{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "design"),
            visibility=Visibility.PUBLIC,
            metadata={"selectors": ("project_slug", "task_slug", "task_bucket"), "kind": "directory"},
        ),
        PathSpec(
            id="task-implementation-changes",
            layout_path=(
                "docs",
                "projects",
                "{project_slug}",
                "tasks",
                "{task_bucket}",
                "{task_slug}",
                "implementation",
                "changes",
            ),
            instantiation_path=("{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "implementation", "changes"),
            visibility=Visibility.PUBLIC,
            metadata={"selectors": ("project_slug", "task_slug", "task_bucket"), "kind": "directory"},
        ),
        PathSpec(
            id="task-backlog",
            layout_path=("docs", "projects", "{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "backlog"),
            instantiation_path=("{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "backlog"),
            visibility=Visibility.PUBLIC,
            metadata={"selectors": ("project_slug", "task_slug", "task_bucket"), "kind": "directory"},
        ),
        PathSpec(
            id="task-features",
            layout_path=("docs", "projects", "{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "features"),
            instantiation_path=("{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "features"),
            visibility=Visibility.PUBLIC,
            metadata={"selectors": ("project_slug", "task_slug", "task_bucket"), "kind": "directory"},
        ),
        PathSpec(
            id="task-assets",
            layout_path=("docs", "projects", "{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "assets"),
            instantiation_path=("{project_slug}", "tasks", "{task_bucket}", "{task_slug}", "assets"),
            visibility=Visibility.PUBLIC,
            metadata={"selectors": ("project_slug", "task_slug", "task_bucket"), "kind": "directory"},
        ),
    )

    return ObjectSpec(
        type="task",
        description="Task lifecycle operations.",
        functions=functions,
        metadata=metadata,
        pathspecs=pathspecs,
    )


TASK_OBJECT_SPEC = build_task_spec()

__all__ = ["TASK_OBJECT_SPEC", "TASK_ARGUMENTS"]
