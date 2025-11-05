"""Object specification for agent identity operations."""

from __future__ import annotations

from typing import Dict, Mapping, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments

AGENT_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "list": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
    ),
    "whoami": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", (), help="Agent slug."),
        ArgumentSpec("process", (), help="Process slug."),
        ArgumentSpec("thread", (), help="Thread slug."),
        ArgumentSpec("receipt_file", ("--receipt-file",), help="Optional path to write whoami receipt."),
    ),
    "create-process": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", (), help="Agent slug."),
        ArgumentSpec("process", ("--process",), help="Process slug.", required=True),
        ArgumentSpec("display_name", ("--display-name",), help="Display name for the process."),
        ArgumentSpec("force", ("--force",), help="Overwrite existing metadata.", expects_value=False, default=False),
    ),
    "create-thread": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", (), help="Agent slug."),
        ArgumentSpec("process", ("--process",), help="Process slug.", required=True),
        ArgumentSpec("thread", ("--thread",), help="Thread slug.", required=True),
        ArgumentSpec("is_main", ("--is-main",), help="Mark thread as main.", expects_value=False, default=False),
        ArgumentSpec("status", ("--status",), help="Thread lifecycle status."),
        ArgumentSpec("execution_mode", ("--execution-mode",), help="Execution mode for the thread."),
        ArgumentSpec("description", ("--description",), help="Thread description."),
        ArgumentSpec("role", ("--role",), help="Assign role slug (repeatable or comma-separated).", multiple=True),
    ),
    "signup": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", (), help="Agent slug."),
        ArgumentSpec("process", ("--process",), help="Process slug.", default="main"),
        ArgumentSpec("thread", ("--thread",), help="Thread slug.", default="main"),
        ArgumentSpec("display_name", ("--display-name",), help="Display name for the process."),
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
        ArgumentSpec("terminal_shell", ("--terminal-shell",), help="Preferred shell for terminal sessions."),
    ),
}


def _argument_metadata(name: str) -> Sequence[Mapping[str, object]]:
    return serialize_arguments(AGENT_ARGUMENTS.get(name, ()))


def build_agent_spec() -> ObjectSpec:
    metadata = {"default_selectors": {"identities_root": "docs/identities"}}

    functions = (
        ObjectFunctionSpec(
            name="list",
            handler_factory="aware_environments.kernel.objects.agent.handlers:list_agents",
            metadata={
                "arguments": _argument_metadata("list"),
            },
        ),
        ObjectFunctionSpec(
            name="whoami",
            handler_factory="aware_environments.kernel.objects.agent.handlers:whoami_handler",
            metadata={
                "arguments": _argument_metadata("whoami"),
            },
        ),
        ObjectFunctionSpec(
            name="create-process",
            handler_factory="aware_environments.kernel.objects.agent.handlers:create_process_handler",
            metadata={
                "arguments": _argument_metadata("create-process"),
                "pathspecs": {
                    "creates": ["agent-dir", "agent-process-dir", "agent-process-json"],
                    "reads": ["agent-file"],
                },
            },
        ),
        ObjectFunctionSpec(
            name="create-thread",
            handler_factory="aware_environments.kernel.objects.agent.handlers:create_thread_handler",
            metadata={
                "arguments": _argument_metadata("create-thread"),
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
            name="signup",
            handler_factory="aware_environments.kernel.objects.agent.handlers:signup_handler",
            metadata={
                "arguments": _argument_metadata("signup"),
                "pathspecs": {
                    "creates": [
                        "agent-dir",
                        "agent-file",
                        "agent-process-dir",
                        "agent-process-json",
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
    )

    pathspecs = (
        PathSpec(
            id="agent-dir",
            layout_path=("docs", "identities", "agents", "{agent}"),
            instantiation_path=("agents", "{agent}"),
            visibility=Visibility.PUBLIC,
            description="Agent directory containing identity and runtime metadata.",
            metadata={"selectors": ("agent",), "kind": "directory"},
        ),
        PathSpec(
            id="agent-file",
            layout_path=("docs", "identities", "agents", "{agent}", "agent.json"),
            instantiation_path=("agents", "{agent}", "agent.json"),
            visibility=Visibility.PUBLIC,
            description="Agent identity record (agent.json).",
            metadata={"selectors": ("agent",)},
        ),
        PathSpec(
            id="agent-process-dir",
            layout_path=("docs", "identities", "agents", "{agent}", "runtime", "process", "{process}"),
            instantiation_path=("agents", "{agent}", "runtime", "process", "{process}"),
            visibility=Visibility.PUBLIC,
            description="Runtime process directory for the agent.",
            metadata={"selectors": ("agent", "process"), "kind": "directory"},
        ),
        PathSpec(
            id="agent-process-json",
            layout_path=(
                "docs",
                "identities",
                "agents",
                "{agent}",
                "runtime",
                "process",
                "{process}",
                "process.json",
            ),
            instantiation_path=("agents", "{agent}", "runtime", "process", "{process}", "process.json"),
            visibility=Visibility.PUBLIC,
            description="Process metadata (process.json).",
            metadata={"selectors": ("agent", "process")},
        ),
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
        type="agent",
        description="Agent identity and process management.",
        functions=functions,
        pathspecs=pathspecs,
        metadata=metadata,
    )


AGENT_OBJECT_SPEC = build_agent_spec()

__all__ = ["AGENT_OBJECT_SPEC", "build_agent_spec"]
