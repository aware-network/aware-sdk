"""Conversation object specification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments


CONVERSATION_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "list": (
        ArgumentSpec("runtime_root", ("--root",), help="Override runtime root."),
        ArgumentSpec("thread", ("--thread",), help="Thread identifier (process/thread)."),
        ArgumentSpec("process_slug", ("--process-slug",), help="Process slug for the thread."),
        ArgumentSpec("thread_slug", ("--thread-slug",), help="Thread slug within the process."),
        ArgumentSpec("since", ("--since",), help="Only include conversations updated after this timestamp."),
    ),
    "resolve": (
        ArgumentSpec("runtime_root", ("--root",), help="Override runtime root."),
        ArgumentSpec("identifier", ("--identifier",), help="Conversation slug or UUID.", required=True),
    ),
    "append": (
        ArgumentSpec("runtime_root", ("--root",), help="Override runtime root."),
        ArgumentSpec("actor_id", ("--actor-id",), help="Actor identifier for the message.", required=True),
        ArgumentSpec("receiver_id", ("--receiver-id",), help="Optional receiver identifier."),
        ArgumentSpec("content", ("--content",), help="Inline message content."),
        ArgumentSpec("content_file", ("--content-file",), help="Path to message content."),
        ArgumentSpec("message_id", ("--message-id",), help="Explicit message UUID."),
        ArgumentSpec("created_at", ("--created-at",), help="Creation timestamp (ISO 8601). Defaults to now."),
        ArgumentSpec("status", ("--status",), help="Message lifecycle status.", default="active"),
        ArgumentSpec("message_type", ("--message-type",), help="Message type label.", default="standard"),
    ),
    "participants": (
        ArgumentSpec("runtime_root", ("--root",), help="Override runtime root."),
        ArgumentSpec("participants", ("--participants",), help="JSON array of participants."),
        ArgumentSpec("participants_file", ("--participants-file",), help="Path to participants JSON."),
    ),
    "repair-participants": (
        ArgumentSpec("runtime_root", ("--root",), help="Override runtime root."),
        ArgumentSpec("dry_run", ("--dry-run",), help="Preview changes without rewriting files.", expects_value=False, default=False),
        ArgumentSpec("limit", ("--limit",), help="Limit number of conversations to repair.", value_type=int),
    ),
    "create": (
        ArgumentSpec("runtime_root", ("--root",), help="Override runtime root."),
        ArgumentSpec("title", ("--title",), help="Conversation title.", required=True),
        ArgumentSpec("description", ("--description",), help="Conversation description."),
        ArgumentSpec("slug", ("--slug",), help="Explicit conversation slug."),
        ArgumentSpec("participants", ("--participants",), help="JSON array of participants."),
        ArgumentSpec("participants_file", ("--participants-file",), help="Path to participants JSON."),
    ),
    "index-refresh": (
        ArgumentSpec("runtime_root", ("--root",), help="Override runtime root."),
        ArgumentSpec("all", ("--all",), help="Refresh index for all threads.", expects_value=False, default=False),
    ),
    "history": (
        ArgumentSpec("runtime_root", ("--root",), help="Override runtime root."),
        ArgumentSpec("since", ("--since",), help="Only include messages after this timestamp."),
        ArgumentSpec("limit", ("--limit",), help="Maximum number of messages to return.", value_type=int),
        ArgumentSpec("format", ("--format",), help="Output format (json|markdown).", default="json"),
    ),
    "doc": (
        ArgumentSpec("runtime_root", ("--root",), help="Override runtime root."),
        ArgumentSpec("format", ("--format",), help="Output format (json|markdown).", default="json"),
    ),
}


def _argument_metadata(name: str) -> Sequence[Mapping[str, object]]:
    return serialize_arguments(CONVERSATION_ARGUMENTS.get(name, ()))


def build_conversation_spec() -> ObjectSpec:
    metadata = {"default_selectors": {"runtime_root": "docs/runtime/process"}}

    functions = (
        ObjectFunctionSpec(
            name="list",
            handler_factory="aware_environments.kernel.objects.conversation.handlers:list_conversations",
            metadata={
                "arguments": _argument_metadata("list"),
            },
        ),
        ObjectFunctionSpec(
            name="resolve",
            handler_factory="aware_environments.kernel.objects.conversation.handlers:resolve",
            metadata={
                "arguments": _argument_metadata("resolve"),
            },
        ),
        ObjectFunctionSpec(
            name="history",
            handler_factory="aware_environments.kernel.objects.conversation.handlers:history",
            metadata={
                "selectors": ("process_slug", "thread_slug", "conversation_slug"),
                "pathspecs": {
                    "reads": ["conversation-doc", "conversation-index"],
                },
                "arguments": _argument_metadata("history"),
            },
        ),
        ObjectFunctionSpec(
            name="append",
            handler_factory="aware_environments.kernel.objects.conversation.handlers:append",
            metadata={
                "selectors": ("process_slug", "thread_slug", "conversation_slug"),
                "pathspecs": {
                    "reads": ["conversation-doc"],
                    "updates": ["conversation-doc", "conversation-index"],
                },
                "arguments": _argument_metadata("append"),
            },
        ),
        ObjectFunctionSpec(
            name="doc",
            handler_factory="aware_environments.kernel.objects.conversation.handlers:document",
            metadata={
                "selectors": ("process_slug", "thread_slug", "conversation_slug"),
                "pathspecs": {
                    "reads": ["conversation-doc"],
                },
                "arguments": _argument_metadata("doc"),
            },
        ),
        ObjectFunctionSpec(
            name="participants",
            handler_factory="aware_environments.kernel.objects.conversation.handlers:participants",
            metadata={
                "selectors": ("process_slug", "thread_slug", "conversation_slug"),
                "pathspecs": {
                    "reads": ["conversation-doc"],
                    "updates": ["conversation-doc", "conversation-index"],
                },
                "arguments": _argument_metadata("participants"),
            },
        ),
        ObjectFunctionSpec(
            name="repair-participants",
            handler_factory="aware_environments.kernel.objects.conversation.handlers:repair_participants",
            metadata={
                "selectors": ("process_slug", "thread_slug", "conversation_slug"),
                "pathspecs": {
                    "reads": ["conversation-doc"],
                    "updates": ["conversation-doc", "conversation-index"],
                },
                "arguments": _argument_metadata("repair-participants"),
            },
        ),
        ObjectFunctionSpec(
            name="create",
            handler_factory="aware_environments.kernel.objects.conversation.handlers:create",
            metadata={
                "selectors": ("process_slug", "thread_slug"),
                "pathspecs": {
                    "reads": ["conversation-dir"],
                    "creates": ["conversation-dir", "conversation-doc"],
                    "updates": ["conversation-dir", "conversation-doc", "conversation-index"],
                },
                "arguments": _argument_metadata("create"),
            },
        ),
        ObjectFunctionSpec(
            name="index-refresh",
            handler_factory="aware_environments.kernel.objects.conversation.handlers:index_refresh",
            metadata={
                "selectors": ("process_slug", "thread_slug"),
                "pathspecs": {
                    "reads": ["conversation-dir", "conversation-doc"],
                    "updates": ["conversation-index"],
                },
                "arguments": _argument_metadata("index-refresh"),
            },
        ),
    )

    pathspecs = (
        PathSpec(
            id="conversation-thread-dir",
            layout_path=("docs", "runtime", "process", "{process_slug}", "threads", "{thread_slug}"),
            instantiation_path=("{process_slug}", "threads", "{thread_slug}"),
            visibility=Visibility.PUBLIC,
            description="Thread directory containing conversations and pane manifests.",
            metadata={"selectors": ("process_slug", "thread_slug"), "kind": "directory"},
        ),
        PathSpec(
            id="conversation-dir",
            layout_path=("docs", "runtime", "process", "{process_slug}", "threads", "{thread_slug}", "conversations"),
            instantiation_path=("{process_slug}", "threads", "{thread_slug}", "conversations"),
            visibility=Visibility.PUBLIC,
            description="Directory holding conversation Markdown logs.",
            metadata={"selectors": ("process_slug", "thread_slug"), "kind": "directory"},
        ),
        PathSpec(
            id="conversation-doc",
            layout_path=(
                "docs",
                "runtime",
                "process",
                "{process_slug}",
                "threads",
                "{thread_slug}",
                "conversations",
                "{conversation_slug}.md",
            ),
            instantiation_path=(
                "{process_slug}",
                "threads",
                "{thread_slug}",
                "conversations",
                "{conversation_slug}.md",
            ),
            visibility=Visibility.PUBLIC,
            description="Markdown conversation log for a specific slug.",
            metadata={"selectors": ("process_slug", "thread_slug", "conversation_slug")},
        ),
        PathSpec(
            id="conversation-index",
            layout_path=(
                "docs",
                "runtime",
                "process",
                "{process_slug}",
                "threads",
                "{thread_slug}",
                "conversations",
                ".index.json",
            ),
            instantiation_path=("{process_slug}", "threads", "{thread_slug}", "conversations", ".index.json"),
            visibility=Visibility.PUBLIC,
            description="Generated conversation index for a thread.",
            metadata={"selectors": ("process_slug", "thread_slug")},
        ),
    )

    return ObjectSpec(
        type="conversation",
        description="Thread conversation management.",
        metadata=metadata,
        functions=functions,
        pathspecs=pathspecs,
    )


CONVERSATION_OBJECT_SPEC = build_conversation_spec()

__all__ = ["CONVERSATION_OBJECT_SPEC", "CONVERSATION_ARGUMENTS"]
