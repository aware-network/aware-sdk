"""Object specification for environment renderers and lock operations."""

from __future__ import annotations

from typing import Dict, Mapping, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments


ENVIRONMENT_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "list": (),
    "describe": (),
    "render-agent": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("agent", ("--agent",), help="Agent slug to render.", required=True),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("thread", ("--thread",), help="Thread slug."),
        ArgumentSpec("root", ("--root",), help="Alias for --identities-root."),
        ArgumentSpec("heading_level", ("--heading-level",), help="Heading level for the guide.", value_type=int),
        ArgumentSpec("context", ("--context",), help="Additional context key=value entries.", multiple=True),
        ArgumentSpec(
            "output_path",
            ("--output", "--out"),
            help="Write rendered markdown to PATH.",
        ),
        ArgumentSpec("write", ("--write",), help="Write canonical AGENT.md.", expects_value=False, default=False),
        ArgumentSpec("print", ("--print",), help="Echo rendered markdown to stdout.", expects_value=False, default=False),
        ArgumentSpec(
            "omit_constitution",
            ("--omit-constitution",),
            help="Skip the environment constitution appendix when rendering.",
            expects_value=False,
            default=False,
        ),
    ),
    "render-role": (
        ArgumentSpec("roles", ("--role",), help="Role slug to render.", multiple=True, required=True),
        ArgumentSpec("heading_level", ("--heading-level",), help="Heading level for sections.", value_type=int),
        ArgumentSpec("output_path", ("--output",), help="Write rendered markdown to PATH."),
        ArgumentSpec("write", ("--write",), help="Write through to output path.", expects_value=False, default=False),
        ArgumentSpec("print", ("--print",), help="Echo rendered markdown to stdout.", expects_value=False, default=False),
    ),
    "render-rule": (
        ArgumentSpec("rule_ids", ("--rule",), help="Rule identifier (repeatable).", multiple=True, required=True),
        ArgumentSpec("fragments", ("--fragment",), help="Render fragments instead of full rules.", expects_value=False, default=False),
        ArgumentSpec("object_filter", ("--object",), help="Restrict fragments to object types.", multiple=True),
        ArgumentSpec("function_refs", ("--function-ref",), help="Restrict fragments to object.function refs.", multiple=True),
        ArgumentSpec("heading_level", ("--heading-level",), help="Heading level for rendered rules.", value_type=int),
        ArgumentSpec("output_path", ("--output",), help="Write rendered markdown to PATH."),
        ArgumentSpec("write", ("--write",), help="Write through to output path.", expects_value=False, default=False),
        ArgumentSpec("print", ("--print",), help="Echo rendered markdown to stdout.", expects_value=False, default=False),
    ),
    "render-object": (
        ArgumentSpec("object", ("--object",), help="Object type to document.", required=True),
        ArgumentSpec("heading_level", ("--heading-level",), help="Heading level for the document.", value_type=int),
        ArgumentSpec("output_path", ("--output",), help="Write rendered markdown to PATH."),
        ArgumentSpec("write", ("--write",), help="Write through to output path.", expects_value=False, default=False),
        ArgumentSpec("print", ("--print",), help="Echo rendered markdown to stdout.", expects_value=False, default=False),
    ),
    "render-guide": (
        ArgumentSpec("aware_root", ("--aware-root",), help="Base directory for guide outputs."),
        ArgumentSpec("output_path", ("--output",), help="Write guide markdown to PATH."),
        ArgumentSpec("write_primary", ("--write",), help="Write AGENTS.md and CLAUDE.md.", expects_value=False, default=False),
        ArgumentSpec("write_cursorrules", ("--write-cursorrules",), help="Write only .cursorrules.", expects_value=False, default=False),
        ArgumentSpec("heading_level", ("--heading-level",), help="Heading level for the guide.", value_type=int),
        ArgumentSpec(
            "compose_agents",
            ("--compose-agents",),
            help="Compose the guide with a default agent appendix.",
            expects_value=False,
            default=False,
        ),
        ArgumentSpec(
            "default_agent",
            ("--default-agent",),
            help="Agent slug to use for the default persona when composing.",
        ),
    ),
    "apply-patch": (
        ArgumentSpec("path", ("--path",), help="Filesystem path to patch.", required=True),
        ArgumentSpec("diff", ("--diff",), help="Inline unified diff content."),
        ArgumentSpec("diff_file", ("--diff-file",), help="Read unified diff from file."),
        ArgumentSpec("policy", ("--policy",), help="Write policy (write_once|append_entry|modifiable)."),
        ArgumentSpec("doc_type", ("--doc-type",), help="Document type for receipts."),
        ArgumentSpec("summary", ("--summary",), help="Optional summary override for receipts."),
    ),
    "render-protocol": (
        ArgumentSpec("protocol_ids", ("--protocol",), help="Protocol slug to render.", multiple=True, required=True),
        ArgumentSpec("output_path", ("--output",), help="Write rendered markdown to PATH."),
        ArgumentSpec("write", ("--write",), help="Write through to output path.", expects_value=False, default=False),
        ArgumentSpec("print", ("--print",), help="Echo rendered markdown to stdout.", expects_value=False, default=False),
    ),
    "environment-lock": (
        ArgumentSpec("aware_root", ("--aware-root",), help="Base directory for lock manifests."),
        ArgumentSpec("output_path", ("--output",), help="Write lock manifest to PATH."),
        ArgumentSpec("write", ("--write",), help="Write canonical .aware/ENV.lock.", expects_value=False, default=False),
        ArgumentSpec("no_write", ("--no-write",), help="Skip writing ENV.lock to disk.", expects_value=False, default=False),
        ArgumentSpec("print", ("--print",), help="Echo lock contents to stdout.", expects_value=False, default=False),
        ArgumentSpec("env_name", ("--environment-name",), help="Override environment name."),
        ArgumentSpec("kernel_ref", ("--kernel-ref",), help="Override kernel reference."),
        ArgumentSpec("version", ("--version",), help="Override environment version."),
    ),
    "rules-lock": (
        ArgumentSpec("aware_root", ("--aware-root",), help="Base directory for lock manifests."),
        ArgumentSpec("output_path", ("--output",), help="Write lock manifest to PATH."),
        ArgumentSpec("write", ("--write",), help="Write canonical .aware/RULES.lock.", expects_value=False, default=False),
        ArgumentSpec("no_write", ("--no-write",), help="Skip writing RULES.lock to disk.", expects_value=False, default=False),
        ArgumentSpec("print", ("--print",), help="Echo lock contents to stdout.", expects_value=False, default=False),
    ),
}


def _argument_metadata(name: str) -> Sequence[Mapping[str, object]]:
    return serialize_arguments(ENVIRONMENT_ARGUMENTS.get(name, ()))


ENVIRONMENT_PATHS = (
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
        instantiation_path=(
            "agents",
            "{agent}",
            "runtime",
            "process",
            "{process}",
            "threads",
            "{thread}",
        ),
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
        description="Thread-scoped agent guide emitted by render-agent.",
        metadata={"selectors": ("agent", "process", "thread"), "kind": "file"},
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
        visibility=Visibility.PUBLIC,
        description="Episodic memory directory for the agent thread.",
        metadata={"selectors": ("agent", "process", "thread"), "kind": "directory"},
    ),
    PathSpec(
        id="environment-guide-agents",
        layout_path=("AGENTS.md",),
        instantiation_path=("AGENTS.md",),
        visibility=Visibility.PRIVATE,
        description="Primary environment guide (AGENTS.md).",
        metadata={"selectors": ("aware_root",), "kind": "file"},
    ),
    PathSpec(
        id="environment-guide-claude",
        layout_path=("CLAUDE.md",),
        instantiation_path=("CLAUDE.md",),
        visibility=Visibility.PRIVATE,
        description="Claude-specific guide emitted by render-guide.",
        metadata={"selectors": ("aware_root",), "kind": "file"},
    ),
    PathSpec(
        id="environment-guide-cursorrules",
        layout_path=(".cursorrules",),
        instantiation_path=(".cursorrules",),
        visibility=Visibility.PRIVATE,
        description="Cursor rules output emitted by render-guide.",
        metadata={"selectors": ("aware_root",), "kind": "file"},
    ),
    PathSpec(
        id="environment-lock-file",
        layout_path=(".aware", "ENV.lock"),
        instantiation_path=(".aware", "ENV.lock"),
        visibility=Visibility.PRIVATE,
        description="Environment lock manifest (ENV.lock).",
        metadata={"selectors": ("aware_root",), "kind": "file"},
    ),
    PathSpec(
        id="rules-lock-file",
        layout_path=(".aware", "RULES.lock"),
        instantiation_path=(".aware", "RULES.lock"),
        visibility=Visibility.PRIVATE,
        description="Rules lock manifest (RULES.lock).",
        metadata={"selectors": ("aware_root",), "kind": "file"},
    ),
)


ENVIRONMENT_OBJECT_SPEC = ObjectSpec(
    type="environment",
    description="Environment renderers, documentation, and lock helpers.",
    functions=(
        ObjectFunctionSpec(
            name="list",
            handler_factory="aware_environments.kernel.objects.environment.handlers:list_environments",
            metadata={"arguments": _argument_metadata("list")},
        ),
        ObjectFunctionSpec(
            name="describe",
            handler_factory="aware_environments.kernel.objects.environment.handlers:describe",
            metadata={"arguments": _argument_metadata("describe")},
        ),
        ObjectFunctionSpec(
            name="render-agent",
            handler_factory="aware_environments.kernel.objects.environment.handlers:render_agent",
            metadata={
                "selectors": ("agent", "process", "thread"),
                "arguments": _argument_metadata("render-agent"),
                "pathspecs": {
                    "writes": ["agent-thread-guide"],
                },
            },
        ),
        ObjectFunctionSpec(
            name="render-role",
            handler_factory="aware_environments.kernel.objects.environment.handlers:render_role",
            metadata={
                "arguments": _argument_metadata("render-role"),
            },
        ),
        ObjectFunctionSpec(
            name="render-rule",
            handler_factory="aware_environments.kernel.objects.environment.handlers:render_rule",
            metadata={
                "arguments": _argument_metadata("render-rule"),
            },
        ),
        ObjectFunctionSpec(
            name="render-object",
            handler_factory="aware_environments.kernel.objects.environment.handlers:render_object",
            metadata={
                "arguments": _argument_metadata("render-object"),
            },
        ),
        ObjectFunctionSpec(
            name="render-guide",
            handler_factory="aware_environments.kernel.objects.environment.handlers:render_guide",
            metadata={
                "selectors": ("aware_root",),
                "arguments": _argument_metadata("render-guide"),
                "pathspecs": {
                    "writes": [
                        "environment-guide-agents",
                        "environment-guide-claude",
                        "environment-guide-cursorrules",
                    ],
                },
            },
        ),
        ObjectFunctionSpec(
            name="apply-patch",
            handler_factory="aware_environments.kernel.objects.environment.handlers:apply_patch",
            metadata={
                "selectors": ("path",),
                "arguments": _argument_metadata("apply-patch"),
            },
        ),
        ObjectFunctionSpec(
            name="render-protocol",
            handler_factory="aware_environments.kernel.objects.environment.handlers:render_protocol",
            metadata={
                "arguments": _argument_metadata("render-protocol"),
            },
        ),
        ObjectFunctionSpec(
            name="environment-lock",
            handler_factory="aware_environments.kernel.objects.environment.handlers:environment_lock",
            metadata={
                "selectors": ("aware_root",),
                "arguments": _argument_metadata("environment-lock"),
                "pathspecs": {
                    "writes": ["environment-lock-file"],
                },
            },
        ),
        ObjectFunctionSpec(
            name="rules-lock",
            handler_factory="aware_environments.kernel.objects.environment.handlers:rules_lock",
            metadata={
                "selectors": ("aware_root",),
                "arguments": _argument_metadata("rules-lock"),
                "pathspecs": {
                    "writes": ["rules-lock-file"],
                },
            },
        ),
    ),
    pathspecs=ENVIRONMENT_PATHS,
    metadata={
        "default_selectors": {
            "identities_root": "docs/identities",
            "aware_root": ".",
        }
    },
)


__all__ = ["ENVIRONMENT_OBJECT_SPEC"]
