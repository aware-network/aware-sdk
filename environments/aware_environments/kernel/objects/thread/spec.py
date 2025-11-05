"""Object specification for runtime thread operations."""

from __future__ import annotations

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments


THREAD_ARGUMENTS = {
    "list": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug filter."),
    ),
    "status": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
    ),
    "branches": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
    ),
    "pane-manifest": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("pane", ("--pane",), help="Pane kind (task, conversation, terminal, etc.).", required=True),
        ArgumentSpec("branch_id", ("--branch-id",), help="Branch identifier (defaults to pane slug when omitted)."),
    ),
    "backlog": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("since", ("--since",), help="ISO timestamp to filter backlog entries."),
    ),
    "branch-set": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("pane", ("--pane",), help="Pane kind to bind.", required=True),
        ArgumentSpec("task", ("--task",), help="Task identifier <project>/<task> to bind."),
        ArgumentSpec("projects_root", ("--projects-root",), help="Override docs/projects root."),
        ArgumentSpec("branch", (), help="Branch payload (JSON object)."),
        ArgumentSpec("pane_manifest", (), help="Pane manifest payload (JSON object)."),
        ArgumentSpec("manifest_version", (), help="Pane manifest version.", value_type=int, default=1),
        ArgumentSpec("task_binding", (), help="Optional thread task binding payload (JSON object)."),
    ),
    "branch-migrate": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("pane", ("--pane",), help="Pane kind to migrate.", required=True),
        ArgumentSpec("conversation", ("--conversation",), help="Conversation identifier to migrate."),
        ArgumentSpec("task", ("--task",), help="Task identifier <project>/<task> to migrate."),
        ArgumentSpec("projects_root", ("--projects-root",), help="Override docs/projects root."),
        ArgumentSpec(
            "migrate_singleton",
            ("--migrate-singleton",),
            help="Migrate legacy singleton manifests into per-branch layout.",
            expects_value=False,
            default=False,
        ),
        ArgumentSpec("branch", (), help="Branch payload (JSON object)."),
        ArgumentSpec("pane_manifest", (), help="Pane manifest payload (JSON object)."),
        ArgumentSpec("manifest_version", (), help="Pane manifest version.", value_type=int, default=1),
        ArgumentSpec("task_binding", (), help="Optional thread task binding payload (JSON object)."),
    ),
    "branch-refresh": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("pane", ("--pane",), help="Pane kind to refresh.", required=True),
        ArgumentSpec("branch_id", ("--branch-id",), help="Optional branch identifier."),
    ),
    "participants-list": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("type", ("--type",), help="Filter participants by type."),
        ArgumentSpec("status", ("--status",), help="Filter participants by status."),
        ArgumentSpec("participant_id", ("--participant-id",), help="Filter by participant identifier."),
        ArgumentSpec(
            "json",
            ("--json",),
            help="Return raw manifest JSON instead of structured payload.",
            expects_value=False,
            default=False,
        ),
    ),
    "participants-bind": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("participant", (), help="Participant payload (JSON object)."),
        ArgumentSpec("participant_type", ("--participant-type",), help="Participant type (agent|human|organization|service)."),
        ArgumentSpec(
            "participant_id",
            ("--participant-id",),
            help="Override participant identifier (defaults to derived slug or UUID).",
        ),
        ArgumentSpec("agent_thread", ("--agent-thread",), help="Agent/process/thread slug (when participant-type=agent)."),
        ArgumentSpec("apt_id", ("--apt-id",), help="Agent process thread UUID (when participant-type=agent)."),
        ArgumentSpec("human_id", ("--human-id",), help="Human UUID (when participant-type=human)."),
        ArgumentSpec("organization_id", ("--organization-id",), help="Organization UUID (when participant-type=organization)."),
        ArgumentSpec("service_id", ("--service-id",), help="Service UUID (when participant-type=service)."),
        ArgumentSpec("role", ("--role",), help="Participant role (executor|controller|observer|other).", multiple=True),
        ArgumentSpec("status", ("--status",), help="Participant status (attached|detached|released|errored|pending)."),
        ArgumentSpec("session_state", ("--session-state",), help="Session state (running|stopping|stopped|unknown)."),
        ArgumentSpec("session_id", ("--session-id",), help="Session identifier."),
        ArgumentSpec("transport", ("--transport",), help="Session transport hint."),
        ArgumentSpec("daemon_pid", ("--daemon-pid",), help="Daemon process id.", value_type=int),
        ArgumentSpec("metadata", ("--metadata",), help="Inline JSON metadata object."),
        ArgumentSpec("metadata_file", ("--metadata-file",), help="Path to JSON metadata file."),
        ArgumentSpec(
            "force",
            ("--force",),
            help="Replace participant if it already exists.",
            expects_value=False,
            default=False,
        ),
    ),
    "participants-update": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("participant_id", ("--participant-id",), help="Participant identifier.", required=True),
        ArgumentSpec("updates", (), help="Participant update payload (JSON object)."),
    ),
    "activity": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("since", ("--since",), help="ISO timestamp to filter activity."),
    ),
    "conversations": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("since", ("--since",), help="ISO timestamp to filter conversations."),
    ),
    "doc": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("path", ("--path",), help="Relative document path.", required=True),
        ArgumentSpec("format", ("--format",), help="Output format (json or markdown).", default="json"),
    ),
}


def _arguments(name: str) -> tuple[dict, ...]:
    return serialize_arguments(THREAD_ARGUMENTS.get(name, ()))


THREAD_PATHS = (
    PathSpec(
        id="thread-dir",
        layout_path=("docs", "runtime", "process", "{process}", "threads", "{thread}"),
        instantiation_path=("runtime", "process", "{process}", "threads", "{thread}"),
        visibility=Visibility.PRIVATE,
        description="Thread directory containing metadata, branches, and backlog entries.",
        metadata={"selectors": ("process", "thread"), "kind": "directory"},
    ),
    PathSpec(
        id="thread-manifest",
        layout_path=("docs", "runtime", "process", "{process}", "threads", "{thread}", "thread.json"),
        instantiation_path=("runtime", "process", "{process}", "threads", "{thread}", "thread.json"),
        visibility=Visibility.PRIVATE,
        description="Thread metadata manifest (thread.json).",
        metadata={"selectors": ("process", "thread")},
    ),
    PathSpec(
        id="thread-branches",
        layout_path=("docs", "runtime", "process", "{process}", "threads", "{thread}", "branches"),
        instantiation_path=("runtime", "process", "{process}", "threads", "{thread}", "branches"),
        visibility=Visibility.PRIVATE,
        description="Thread branch directory containing pane descriptors.",
        metadata={"selectors": ("process", "thread"), "kind": "directory"},
    ),
    PathSpec(
        id="thread-pane-manifests",
        layout_path=("docs", "runtime", "process", "{process}", "threads", "{thread}", "pane_manifests"),
        instantiation_path=("runtime", "process", "{process}", "threads", "{thread}", "pane_manifests"),
        visibility=Visibility.PRIVATE,
        description="Thread pane manifest directory.",
        metadata={"selectors": ("process", "thread"), "kind": "directory"},
    ),
    PathSpec(
        id="thread-participants",
        layout_path=("docs", "runtime", "process", "{process}", "threads", "{thread}", "participants.json"),
        instantiation_path=("runtime", "process", "{process}", "threads", "{thread}", "participants.json"),
        visibility=Visibility.PRIVATE,
        description="Thread participants manifest.",
        metadata={"selectors": ("process", "thread")},
    ),
    PathSpec(
        id="thread-backlog",
        layout_path=("docs", "runtime", "process", "{process}", "threads", "{thread}", "backlog"),
        instantiation_path=("runtime", "process", "{process}", "threads", "{thread}", "backlog"),
        visibility=Visibility.PRIVATE,
        description="Thread backlog entries captured as markdown.",
        metadata={"selectors": ("process", "thread"), "kind": "directory"},
    ),
    PathSpec(
        id="thread-conversations-dir",
        layout_path=("docs", "runtime", "process", "{process}", "threads", "{thread}", "conversations"),
        instantiation_path=("runtime", "process", "{process}", "threads", "{thread}", "conversations"),
        visibility=Visibility.PRIVATE,
        description="Thread conversation markdown directory.",
        metadata={"selectors": ("process", "thread"), "kind": "directory"},
    ),
)


THREAD_OBJECT_SPEC = ObjectSpec(
    type="thread",
    description="Thread runtime metadata and backlog inspection.",
    functions=(
        ObjectFunctionSpec(
            name="list",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_list_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime",),
                "selectors": ("process",),
                "arguments": _arguments("list"),
                "pathspecs": {"reads": ("thread-dir",)},
            },
        ),
        ObjectFunctionSpec(
            name="status",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_status_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime",),
                "selectors": ("process", "thread"),
                "arguments": _arguments("status"),
                "pathspecs": {"reads": ("thread-dir", "thread-manifest", "thread-branches")},
            },
        ),
        ObjectFunctionSpec(
            name="activity",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_activity_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime",),
                "selectors": ("process", "thread"),
                "arguments": _arguments("activity"),
                "pathspecs": {
                    "reads": (
                        "thread-dir",
                        "thread-backlog",
                        "thread-conversations-dir",
                    )
                },
            },
        ),
        ObjectFunctionSpec(
            name="branches",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_branches_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime",),
                "selectors": ("process", "thread"),
                "arguments": _arguments("branches"),
                "pathspecs": {"reads": ("thread-branches", "thread-pane-manifests")},
            },
        ),
        ObjectFunctionSpec(
            name="pane-manifest",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_pane_manifest_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime",),
                "selectors": ("process", "thread"),
                "arguments": _arguments("pane-manifest"),
                "pathspecs": {"reads": ("thread-pane-manifests",)},
            },
        ),
        ObjectFunctionSpec(
            name="backlog",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_backlog_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime",),
                "selectors": ("process", "thread"),
                "arguments": _arguments("backlog"),
                "pathspecs": {"reads": ("thread-backlog",)},
            },
        ),
        ObjectFunctionSpec(
            name="conversations",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_conversations_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime",),
                "selectors": ("process", "thread"),
                "arguments": _arguments("conversations"),
                "pathspecs": {"reads": ("thread-conversations-dir",)},
            },
        ),
        ObjectFunctionSpec(
            name="doc",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_document_handler",
            metadata={
                "selectors": ("process", "thread"),
                "arguments": _arguments("doc"),
                "rule_ids": ("01-thread-01-runtime",),
                "pathspecs": {"reads": ("thread-dir",)},
            },
        ),
        ObjectFunctionSpec(
            name="branch-set",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_branch_set_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime", "02-task-03-change-tracking"),
                "selectors": ("process", "thread"),
                "arguments": _arguments("branch-set"),
                "pathspecs": {
                    "updates": ("thread-branches", "thread-pane-manifests", "thread-dir"),
                },
            },
        ),
        ObjectFunctionSpec(
            name="branch-migrate",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_branch_migrate_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime", "02-task-03-change-tracking"),
                "selectors": ("process", "thread"),
                "arguments": _arguments("branch-migrate"),
                "pathspecs": {
                    "updates": ("thread-branches", "thread-pane-manifests", "thread-dir"),
                },
            },
        ),
        ObjectFunctionSpec(
            name="branch-refresh",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_branch_refresh_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime", "02-task-03-change-tracking"),
                "selectors": ("process", "thread"),
                "arguments": _arguments("branch-refresh"),
                "pathspecs": {
                    "updates": ("thread-branches", "thread-pane-manifests"),
                },
            },
        ),
        ObjectFunctionSpec(
            name="participants-list",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_participants_list_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime",),
                "selectors": ("process", "thread"),
                "arguments": _arguments("participants-list"),
                "pathspecs": {"reads": ("thread-participants",)},
            },
        ),
        ObjectFunctionSpec(
            name="participants-bind",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_participants_bind_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime", "02-task-03-change-tracking"),
                "selectors": ("process", "thread"),
                "arguments": _arguments("participants-bind"),
                "pathspecs": {"updates": ("thread-participants",)},
            },
        ),
        ObjectFunctionSpec(
            name="participants-update",
            handler_factory="aware_environments.kernel.objects.thread.handlers:thread_participants_update_handler",
            metadata={
                "rule_ids": ("01-thread-01-runtime", "02-task-03-change-tracking"),
                "selectors": ("process", "thread"),
                "arguments": _arguments("participants-update"),
                "pathspecs": {"updates": ("thread-participants",)},
            },
        ),
    ),
    pathspecs=THREAD_PATHS,
    metadata={},
)


__all__ = ["THREAD_OBJECT_SPEC"]
