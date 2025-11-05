"""Object specification for agent process thread operations."""

from __future__ import annotations

from typing import Dict, Mapping, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments


AGENT_THREAD_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "signup": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", (), help="Agent slug."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("display_name", ("--display-name",), help="Process display name."),
        ArgumentSpec("is_main", ("--is-main",), help="Mark thread as main.", expects_value=False, default=False),
        ArgumentSpec("status", ("--status",), help="Thread lifecycle status."),
        ArgumentSpec("execution_mode", ("--execution-mode",), help="Execution mode for the thread."),
        ArgumentSpec("description", ("--description",), help="Thread description."),
        ArgumentSpec("force", ("--force",), help="Overwrite existing metadata.", expects_value=False, default=False),
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("aware_root", ("--aware-root",), help="Override aware root."),
        ArgumentSpec("provider", ("--provider",), help="Terminal provider slug."),
        ArgumentSpec("with_terminal", ("--with-terminal",), help="Ensure terminal binding with identifier."),
        ArgumentSpec(
            "allow_missing_session",
            ("--allow-missing-session",),
            help="Allow terminal binding without an active provider session.",
            expects_value=False,
            default=False,
        ),
    ),
    "login": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("aware_root", ("--aware-root",), help="Override aware home root."),
        ArgumentSpec("agent", (), help="Agent slug."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("provider", ("--provider",), help="Terminal provider slug.", required=True),
        ArgumentSpec("terminal_id", ("--terminal-id",), help="Terminal identifier."),
        ArgumentSpec(
            "ensure_terminal",
            ("--ensure-terminal",),
            help="Ensure terminal descriptor exists.",
            expects_value=False,
            default=True,
        ),
        ArgumentSpec(
            "no_ensure_terminal",
            ("--no-ensure-terminal",),
            help="Skip ensuring terminal descriptor.",
            expects_value=False,
            default=False,
        ),
        ArgumentSpec(
            "allow_missing_session",
            ("--allow-missing-session",),
            help="Permit missing session receipts.",
            expects_value=False,
            default=False,
        ),
        ArgumentSpec(
            "skip_resolve",
            ("--skip-resolve",),
            help="Skip session resolution during login.",
            expects_value=False,
            default=False,
        ),
        ArgumentSpec(
            "resume",
            ("--resume",),
            help="Resume existing terminal session if present.",
            expects_value=False,
            default=False,
        ),
        ArgumentSpec("metadata", ("--metadata",), help="Additional metadata JSON or key=value pairs."),
        ArgumentSpec("metadata_file", ("--metadata-file",), help="Path to metadata JSON file."),
    ),
    "session-update": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", (), help="Agent slug."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("session_id", ("--session-id",), help="Provider session identifier."),
        ArgumentSpec("provider", ("--provider",), help="Terminal provider slug."),
        ArgumentSpec("terminal_id", ("--terminal-id",), help="Terminal identifier."),
        ArgumentSpec("metadata", ("--metadata",), help="Additional metadata JSON or key=value pairs."),
        ArgumentSpec("metadata_file", ("--metadata-file",), help="Path to metadata JSON file."),
    ),
}


def _argument_metadata(name: str) -> Sequence[Mapping[str, object]]:
    return serialize_arguments(AGENT_THREAD_ARGUMENTS.get(name, ()))


def build_agent_thread_spec() -> ObjectSpec:
    metadata = {"default_selectors": {"identities_root": "docs/identities"}}

    functions = (
        ObjectFunctionSpec(
            name="signup",
            handler_factory="aware_environments.kernel.objects.agent_thread.handlers:signup",
            metadata={
                "selectors": ("agent",),
                "arguments": _argument_metadata("signup"),
                "pathspecs": {
                    "creates": [
                        "agent-thread-dir",
                        "agent-thread-metadata",
                        "agent-thread-roles",
                        "agent-thread-guide",
                        "agent-thread-working",
                        "agent-thread-episodic",
                    ],
                    "updates": [
                        "agent-thread-metadata",
                        "agent-thread-guide",
                        "agent-thread-working",
                    ],
                },
            },
        ),
        ObjectFunctionSpec(
            name="login",
            handler_factory="aware_environments.kernel.objects.agent_thread.handlers:login",
            metadata={
                "selectors": ("agent",),
                "arguments": _argument_metadata("login"),
                "pathspecs": {
                    "reads": ["agent-thread-dir", "agent-thread-metadata"],
                    "updates": ["agent-thread-metadata"],
                },
            },
        ),
        ObjectFunctionSpec(
            name="session-update",
            handler_factory="aware_environments.kernel.objects.agent_thread.handlers:session_update",
            metadata={
                "selectors": ("agent",),
                "arguments": _argument_metadata("session-update"),
                "pathspecs": {
                    "updates": ["agent-thread-metadata"],
                },
            },
        ),
    )

    pathspecs = (
        PathSpec(
            id="agent-thread-dir",
            layout_path=(
                "docs",
                "identities",
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "threads",
                "{thread}",
            ),
            instantiation_path=("agents", "{agent}", "runtime", "process", "{process}", "threads", "{thread}"),
            visibility=Visibility.PUBLIC,
            description="Thread directory for the agent process.",
            metadata={"selectors": ("agent", "process", "thread"), "kind": "directory"},
        ),
        PathSpec(
            id="agent-thread-metadata",
            layout_path=(
                "docs",
                "identities",
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "threads",
                "{thread}",
                "agent_process_thread.json",
            ),
            instantiation_path=(
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "threads",
                "{thread}",
                "agent_process_thread.json",
            ),
            visibility=Visibility.PUBLIC,
            description="Thread metadata document (agent_process_thread.json).",
            metadata={"selectors": ("agent", "process", "thread")},
        ),
        PathSpec(
            id="agent-thread-roles",
            layout_path=(
                "docs",
                "identities",
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "threads",
                "{thread}",
                "roles.json",
            ),
            instantiation_path=(
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "threads",
                "{thread}",
                "roles.json",
            ),
            visibility=Visibility.PUBLIC,
            description="Thread roles manifest (roles.json).",
            metadata={"selectors": ("agent", "process", "thread")},
        ),
        PathSpec(
            id="agent-thread-guide",
            layout_path=(
                "docs",
                "identities",
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "threads",
                "{thread}",
                "AGENT.md",
            ),
            instantiation_path=(
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "threads",
                "{thread}",
                "AGENT.md",
            ),
            visibility=Visibility.PUBLIC,
            description="Thread-scoped agent guide.",
            metadata={"selectors": ("agent", "process", "thread")},
        ),
        PathSpec(
            id="agent-thread-working",
            layout_path=(
                "docs",
                "identities",
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "threads",
                "{thread}",
                "working_memory.md",
            ),
            instantiation_path=(
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "threads",
                "{thread}",
                "working_memory.md",
            ),
            visibility=Visibility.PUBLIC,
            description="Working memory snapshot for the agent thread.",
            metadata={"selectors": ("agent", "process", "thread")},
        ),
        PathSpec(
            id="agent-thread-episodic",
            layout_path=(
                "docs",
                "identities",
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "threads",
                "{thread}",
                "episodic",
            ),
            instantiation_path=(
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "threads",
                "{thread}",
                "episodic",
            ),
            visibility=Visibility.PRIVATE,
            description="Episodic memory directory for the agent thread.",
            metadata={"selectors": ("agent", "process", "thread"), "kind": "directory"},
        ),
    )

    return ObjectSpec(
        type="agent-thread",
        description="Agent process thread lifecycle and session management.",
        functions=functions,
        pathspecs=pathspecs,
        metadata=metadata,
    )


AGENT_THREAD_OBJECT_SPEC = build_agent_thread_spec()

__all__ = ["AGENT_THREAD_OBJECT_SPEC", "build_agent_thread_spec"]
