"""Object specification for agent-thread-memory operations."""

from __future__ import annotations

from typing import Dict, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments

MEMORY_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "status": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", ("--agent",), help="Agent slug.", required=True),
        ArgumentSpec("process", ("--process",), help="Process slug.", required=True),
        ArgumentSpec("thread", ("--thread",), help="Thread slug.", required=True),
        ArgumentSpec("limit", ("--limit",), help="Number of episodic entries to include.", value_type=int, default=5),
    ),
    "history": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", ("--agent",), help="Agent slug.", required=True),
        ArgumentSpec("process", ("--process",), help="Process slug.", required=True),
        ArgumentSpec("thread", ("--thread",), help="Thread slug.", required=True),
        ArgumentSpec("limit", ("--limit",), help="Number of episodic entries to list.", value_type=int, default=20),
        ArgumentSpec("significance", ("--significance",), help="Filter episodic history by significance."),
        ArgumentSpec("session_type", ("--session-type",), help="Filter episodic history by session type."),
    ),
    "write-working": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", ("--agent",), help="Agent slug.", required=True),
        ArgumentSpec("process", ("--process",), help="Process slug.", required=True),
        ArgumentSpec("thread", ("--thread",), help="Thread slug.", required=True),
        ArgumentSpec("content", ("--content",), help="Inline working memory content."),
        ArgumentSpec("content_file", ("--content-file",), help="Path to file with working memory content."),
        ArgumentSpec("author_agent", ("--author-agent",), help="Author agent slug."),
        ArgumentSpec("author_process", ("--author-process",), help="Author process slug."),
        ArgumentSpec("author_thread", ("--author-thread",), help="Author thread slug."),
    ),
    "append-episodic": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", ("--agent",), help="Agent slug.", required=True),
        ArgumentSpec("process", ("--process",), help="Process slug.", required=True),
        ArgumentSpec("thread", ("--thread",), help="Thread slug.", required=True),
        ArgumentSpec("title", ("--title",), help="Title for the episodic entry.", required=True),
        ArgumentSpec("content", ("--content",), help="Inline episodic entry content."),
        ArgumentSpec("content_file", ("--content-file",), help="Path to file with episodic entry content."),
        ArgumentSpec("author_agent", ("--author-agent",), help="Author agent slug."),
        ArgumentSpec("author_process", ("--author-process",), help="Author process slug."),
        ArgumentSpec("author_thread", ("--author-thread",), help="Author thread slug."),
        ArgumentSpec("session_type", ("--session-type",), help="Session type for the episodic entry."),
        ArgumentSpec("significance", ("--significance",), help="Significance level for the episodic entry."),
    ),
    "diff": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", ("--agent",), help="Agent slug.", required=True),
        ArgumentSpec("process", ("--process",), help="Process slug.", required=True),
        ArgumentSpec("thread", ("--thread",), help="Thread slug.", required=True),
        ArgumentSpec("since", ("--since",), help="ISO timestamp to diff from.", required=True),
    ),
    "validate": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", ("--agent",), help="Agent slug.", required=True),
        ArgumentSpec("process", ("--process",), help="Process slug.", required=True),
        ArgumentSpec("thread", ("--thread",), help="Thread slug.", required=True),
    ),
}


def _argument_metadata(function_name: str):
    return serialize_arguments(MEMORY_ARGUMENTS.get(function_name, ()))


def build_agent_thread_memory_spec() -> ObjectSpec:
    metadata = {"default_selectors": {"identities_root": "docs/identities"}}

    functions = (
        ObjectFunctionSpec(
            name="status",
            handler_factory="aware_environments.kernel.objects.agent_thread_memory.handlers:memory_status",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy",),
                "selectors": ("agent", "process", "thread"),
                "arguments": _argument_metadata("status"),
                "pathspecs": {
                    "reads": ("agent-thread-working", "agent-thread-episodic"),
                },
            },
        ),
        ObjectFunctionSpec(
            name="history",
            handler_factory="aware_environments.kernel.objects.agent_thread_memory.handlers:memory_history",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy",),
                "selectors": ("agent", "process", "thread"),
                "arguments": _argument_metadata("history"),
                "pathspecs": {
                    "reads": ("agent-thread-episodic",),
                },
            },
        ),
        ObjectFunctionSpec(
            name="write-working",
            handler_factory="aware_environments.kernel.objects.agent_thread_memory.handlers:memory_write_working",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy",),
                "selectors": ("agent", "process", "thread"),
                "arguments": _argument_metadata("write-working"),
                "pathspecs": {
                    "updates": ("agent-thread-working",),
                    "reads": ("agent-thread-working",),
                },
            },
        ),
        ObjectFunctionSpec(
            name="append-episodic",
            handler_factory="aware_environments.kernel.objects.agent_thread_memory.handlers:memory_append_episodic",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy",),
                "selectors": ("agent", "process", "thread"),
                "arguments": _argument_metadata("append-episodic"),
                "pathspecs": {
                    "updates": ("agent-thread-episodic",),
                    "reads": ("agent-thread-episodic",),
                },
            },
        ),
        ObjectFunctionSpec(
            name="diff",
            handler_factory="aware_environments.kernel.objects.agent_thread_memory.handlers:memory_diff",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy",),
                "selectors": ("agent", "process", "thread"),
                "arguments": _argument_metadata("diff"),
                "pathspecs": {
                    "reads": ("agent-thread-working", "agent-thread-episodic"),
                },
            },
        ),
        ObjectFunctionSpec(
            name="validate",
            handler_factory="aware_environments.kernel.objects.agent_thread_memory.handlers:memory_validate",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy",),
                "selectors": ("agent", "process", "thread"),
                "arguments": _argument_metadata("validate"),
                "pathspecs": {
                    "reads": ("agent-thread-working", "agent-thread-episodic"),
                },
            },
        ),
    )

    pathspecs = (
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
        type="agent-thread-memory",
        description="Agent thread working and episodic memory management.",
        functions=functions,
        pathspecs=pathspecs,
        metadata=metadata,
    )


AGENT_THREAD_MEMORY_OBJECT_SPEC = build_agent_thread_memory_spec()

__all__ = ["AGENT_THREAD_MEMORY_OBJECT_SPEC"]
