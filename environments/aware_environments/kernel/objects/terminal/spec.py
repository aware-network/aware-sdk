"""Terminal object specification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments


TERMINAL_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "create": (
        ArgumentSpec("thread_identifier", ("--thread-id",), help="Thread identifier or UUID.", required=True),
        ArgumentSpec("terminal_id", ("--terminal-id",), help="Terminal identifier (auto-generated when omitted)."),
        ArgumentSpec("name", ("--name",), help="Friendly terminal name."),
        ArgumentSpec("cwd", ("--cwd",), help="Working directory for the session."),
        ArgumentSpec("shell", ("--shell",), help="Shell executable.", default="/bin/bash"),
        ArgumentSpec("env", ("--env",), help="Environment KEY=VALUE pairs.", multiple=True),
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override docs/runtime root."),
        ArgumentSpec("aware_root", ("--aware-root",), help="Override aware home directory."),
    ),
    "list": (
        ArgumentSpec("thread_identifier", ("--thread-id",), help="Thread identifier or UUID.", required=True),
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override docs/runtime root."),
        ArgumentSpec("aware_root", ("--aware-root",), help="Override aware home directory."),
    ),
    "attach": (
        ArgumentSpec("thread_identifier", ("--thread-id",), help="Thread identifier or UUID.", required=True),
        ArgumentSpec("terminal_id", ("--terminal-id",), help="Terminal identifier.", required=True),
        ArgumentSpec("cwd", ("--cwd",), help="Working directory override."),
        ArgumentSpec("shell", ("--shell",), help="Shell executable override."),
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override docs/runtime root."),
        ArgumentSpec("aware_root", ("--aware-root",), help="Override aware home directory."),
    ),
    "delete": (
        ArgumentSpec("thread_identifier", ("--thread-id",), help="Thread identifier or UUID.", required=True),
        ArgumentSpec("terminal_id", ("--terminal-id",), help="Terminal identifier.", required=True),
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override docs/runtime root."),
        ArgumentSpec("aware_root", ("--aware-root",), help="Override aware home directory."),
        ArgumentSpec("remove_session", ("--remove-session",), help="Remove participant session metadata.", expects_value=False),
        ArgumentSpec("kill_window", ("--kill-window",), help="Kill tmux window after removal.", expects_value=False),
    ),
    "bind-provider": (
        ArgumentSpec("thread_identifier", ("--thread-id",), help="Thread identifier or UUID.", required=True),
        ArgumentSpec("terminal_id", ("--terminal-id",), help="Terminal identifier.", required=True),
        ArgumentSpec("apt_id", ("--apt-id",), help="Agent participant identifier.", required=True),
        ArgumentSpec("provider", ("--provider",), help="Provider slug to bind."),
        ArgumentSpec("resume", ("--resume",), help="Resume existing provider session.", expects_value=False),
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override docs/runtime root."),
        ArgumentSpec("aware_root", ("--aware-root",), help="Override aware home directory."),
        ArgumentSpec("identities_root", ("--identities-root",), help="Override docs/identities root."),
        ArgumentSpec("metadata", ("--metadata",), help="Additional provider metadata JSON."),
        ArgumentSpec("metadata_file", ("--metadata-file",), help="Path to JSON file with metadata."),
    ),
    "session-ensure": (
        ArgumentSpec("thread_identifier", ("--thread-id",), help="Thread identifier or UUID.", required=True),
        ArgumentSpec("apt_id", ("--apt-id",), help="Agent participant identifier.", required=True),
        ArgumentSpec("provider", ("--provider",), help="Provider slug to ensure.", required=True),
        ArgumentSpec("terminal_id", ("--terminal-id",), help="Terminal identifier."),
        ArgumentSpec("resume", ("--resume",), help="Resume existing provider session.", expects_value=False),
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override docs/runtime root."),
        ArgumentSpec("aware_root", ("--aware-root",), help="Override aware home directory."),
        ArgumentSpec("identities_root", ("--identities-root",), help="Override docs/identities root."),
        ArgumentSpec("metadata", ("--metadata",), help="Additional provider metadata JSON."),
        ArgumentSpec("metadata_file", ("--metadata-file",), help="Path to JSON file with metadata."),
    ),
    "session-resolve": (
        ArgumentSpec("thread_identifier", ("--thread-id",), help="Thread identifier or UUID.", required=True),
        ArgumentSpec("provider", ("--provider",), help="Provider slug to resolve.", required=True),
        ArgumentSpec("terminal_id", ("--terminal-id",), help="Terminal identifier."),
        ArgumentSpec("apt_id", ("--apt-id",), help="Agent participant identifier."),
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override docs/runtime root."),
        ArgumentSpec("aware_root", ("--aware-root",), help="Override aware home directory."),
        ArgumentSpec("identities_root", ("--identities-root",), help="Override docs/identities root."),
    ),
}


def _argument_metadata(name: str) -> Sequence[Mapping[str, object]]:
    return serialize_arguments(TERMINAL_ARGUMENTS.get(name, ()))


def build_terminal_spec() -> ObjectSpec:
    metadata = {
        "default_selectors": {
            "runtime_root": "docs/runtime/process",
            "aware_root": ".aware",
            "identities_root": "docs/identities",
        }
    }

    functions = (
        ObjectFunctionSpec(
            name="create",
            handler_factory="aware_environments.kernel.objects.terminal.handlers:create_terminal",
            metadata={
                "rule_ids": ("02-agent-01-identity",),
                "selectors": ("thread_identifier", "terminal_id"),
                "pathspecs": {
                    "creates": (
                        "terminal-descriptor",
                        "terminal-pane-manifest",
                        "terminal-branch",
                    ),
                    "reads": ("thread-terminals-dir",),
                },
                "arguments": _argument_metadata("create"),
            },
        ),
        ObjectFunctionSpec(
            name="list",
            handler_factory="aware_environments.kernel.objects.terminal.handlers:list_terminals",
            metadata={
                "rule_ids": ("02-agent-01-identity",),
                "selectors": ("thread_identifier",),
                "pathspecs": {"reads": ("thread-terminals-dir",)},
                "arguments": _argument_metadata("list"),
            },
        ),
        ObjectFunctionSpec(
            name="attach",
            handler_factory="aware_environments.kernel.objects.terminal.handlers:attach_terminal",
            metadata={
                "rule_ids": ("02-agent-01-identity",),
                "selectors": ("thread_identifier", "terminal_id"),
                "pathspecs": {
                    "reads": ("terminal-descriptor",),
                    "updates": ("terminal-descriptor", "terminal-pane-manifest"),
                },
                "arguments": _argument_metadata("attach"),
            },
        ),
        ObjectFunctionSpec(
            name="delete",
            handler_factory="aware_environments.kernel.objects.terminal.handlers:delete_terminal",
            metadata={
                "rule_ids": ("02-agent-01-identity",),
                "selectors": ("thread_identifier", "terminal_id"),
                "pathspecs": {
                    "reads": ("terminal-descriptor",),
                    "updates": ("terminal-descriptor", "terminal-pane-manifest", "terminal-branch"),
                },
                "arguments": _argument_metadata("delete"),
            },
        ),
        ObjectFunctionSpec(
            name="bind-provider",
            handler_factory="aware_environments.kernel.objects.terminal.handlers:bind_provider",
            metadata={
                "rule_ids": ("02-agent-01-identity",),
                "selectors": ("thread_identifier", "terminal_id", "provider"),
                "pathspecs": {
                    "reads": ("terminal-descriptor", "participants-manifest"),
                    "updates": ("terminal-descriptor", "participants-manifest"),
                },
                "arguments": _argument_metadata("bind-provider"),
            },
        ),
        ObjectFunctionSpec(
            name="session-ensure",
            handler_factory="aware_environments.kernel.objects.terminal.handlers:ensure_terminal_session",
            metadata={
                "rule_ids": ("02-agent-01-identity",),
                "selectors": ("thread_identifier", "provider"),
                "pathspecs": {
                    "reads": ("terminal-descriptor", "participants-manifest"),
                    "updates": ("terminal-descriptor", "participants-manifest", "terminal-pane-manifest"),
                },
                "arguments": _argument_metadata("session-ensure"),
            },
        ),
        ObjectFunctionSpec(
            name="session-resolve",
            handler_factory="aware_environments.kernel.objects.terminal.handlers:session_resolve",
            metadata={
                "rule_ids": ("02-agent-01-identity",),
                "selectors": ("thread_identifier", "provider"),
                "pathspecs": {
                    "reads": ("terminal-descriptor", "participants-manifest"),
                },
                "arguments": _argument_metadata("session-resolve"),
            },
        ),
    )

    pathspecs = (
        PathSpec(
            id="thread-terminals-dir",
            layout_path=("docs", "runtime", "process", "{process_slug}", "threads", "{thread_slug}", "terminals"),
            instantiation_path=("runtime", "process", "{process_slug}", "threads", "{thread_slug}", "terminals"),
            visibility=Visibility.PRIVATE,
            description="Thread terminal descriptor directory.",
            metadata={"selectors": ("process_slug", "thread_slug"), "kind": "directory"},
        ),
        PathSpec(
            id="terminal-descriptor",
            layout_path=("docs", "runtime", "process", "{process_slug}", "threads", "{thread_slug}", "terminals", "{terminal_slug}.json"),
            instantiation_path=("runtime", "process", "{process_slug}", "threads", "{thread_slug}", "terminals", "{terminal_slug}.json"),
            visibility=Visibility.PRIVATE,
            description="Terminal descriptor JSON.",
            metadata={"selectors": ("process_slug", "thread_slug", "terminal_slug")},
        ),
        PathSpec(
            id="terminal-pane-manifest",
            layout_path=("docs", "runtime", "process", "{process_slug}", "threads", "{thread_slug}", "pane_manifests", "{terminal_slug}.json"),
            instantiation_path=("runtime", "process", "{process_slug}", "threads", "{thread_slug}", "pane_manifests", "{terminal_slug}.json"),
            visibility=Visibility.PRIVATE,
            description="Pane manifest for terminal pane integration.",
            metadata={"selectors": ("process_slug", "thread_slug", "terminal_slug")},
        ),
        PathSpec(
            id="terminal-branch",
            layout_path=("docs", "runtime", "process", "{process_slug}", "threads", "{thread_slug}", "branches", "{terminal_slug}.json"),
            instantiation_path=("runtime", "process", "{process_slug}", "threads", "{thread_slug}", "branches", "{terminal_slug}.json"),
            visibility=Visibility.PRIVATE,
            description="Terminal branch manifest.",
            metadata={"selectors": ("process_slug", "thread_slug", "terminal_slug")},
        ),
        PathSpec(
            id="participants-manifest",
            layout_path=("docs", "runtime", "process", "{process_slug}", "threads", "{thread_slug}", "participants.json"),
            instantiation_path=("runtime", "process", "{process_slug}", "threads", "{thread_slug}", "participants.json"),
            visibility=Visibility.PRIVATE,
            description="Thread participants manifest.",
            metadata={"selectors": ("process_slug", "thread_slug")},
        ),
    )

    return ObjectSpec(
        type="terminal",
        description="Terminal daemon and session lifecycle management.",
        metadata=metadata,
        functions=functions,
        pathspecs=pathspecs,
    )


TERMINAL_OBJECT_SPEC = build_terminal_spec()

__all__ = ["TERMINAL_OBJECT_SPEC", "TERMINAL_ARGUMENTS"]
