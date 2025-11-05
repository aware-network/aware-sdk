"""Object specification for rule registry metadata and fragments."""

from __future__ import annotations

from typing import Dict, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments


RULE_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "list": (
        ArgumentSpec("rules_root", ("--rules-root",), help="Override rules root (legacy)."),
        ArgumentSpec("refresh", ("--refresh",), help="Force rescan of rule metadata.", expects_value=False, default=False),
    ),
    "fragments": (
        ArgumentSpec("rule_ids", ("--rule",), help="Rule identifier.", multiple=True),
        ArgumentSpec("object_types", ("--object",), help="Filter fragments by object type.", multiple=True),
        ArgumentSpec(
            "function_refs",
            ("--function",),
            help="Filter fragments by function (object:function).",
            multiple=True,
        ),
    ),
}


def _argument_metadata(name: str):
    return serialize_arguments(RULE_ARGUMENTS.get(name, ()))


def build_rule_spec() -> ObjectSpec:
    metadata = {"default_selectors": {}}

    functions = (
        ObjectFunctionSpec(
            name="list",
            handler_factory="aware_environments.kernel.objects.rule.handlers:list_rules",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "arguments": _argument_metadata("list"),
                "pathspecs": {
                    "reads": ("rules-root", "rules-current-dir", "rules-templates-dir"),
                },
            },
        ),
        ObjectFunctionSpec(
            name="fragments",
            handler_factory="aware_environments.kernel.objects.rule.handlers:fragments",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "selectors": ("rule",),
                "arguments": _argument_metadata("fragments"),
                "pathspecs": {
                    "reads": ("rules-root", "rules-current-dir", "rules-templates-dir"),
                },
            },
        ),
    )

    pathspecs = (
        PathSpec(
            id="rules-root",
            layout_path=("docs", "rules"),
            instantiation_path=("docs", "rules"),
            visibility=Visibility.PUBLIC,
            description="Root directory containing rule documentation.",
            metadata={"kind": "directory"},
        ),
        PathSpec(
            id="rules-current-dir",
            layout_path=("environments", "aware_environments", "kernel", "rules", "current"),
            instantiation_path=("environments", "aware_environments", "kernel", "rules", "current"),
            visibility=Visibility.PRIVATE,
            description="Current rule templates bundled with the kernel environment.",
            metadata={"kind": "directory"},
        ),
        PathSpec(
            id="rules-templates-dir",
            layout_path=("environments", "aware_environments", "kernel", "rules", "templates"),
            instantiation_path=("environments", "aware_environments", "kernel", "rules", "templates"),
            visibility=Visibility.PRIVATE,
            description="Rule constitution templates bundled with the kernel environment.",
            metadata={"kind": "directory"},
        ),
        PathSpec(
            id="rules-versions-dir",
            layout_path=("environments", "aware_environments", "kernel", "rules", "versions"),
            instantiation_path=("environments", "aware_environments", "kernel", "rules", "versions"),
            visibility=Visibility.PRIVATE,
            description="Historical rule versions bundled with the kernel environment.",
            metadata={"kind": "directory"},
        ),
    )

    return ObjectSpec(
        type="rule",
        description="Rule catalog inspection and fragment rendering.",
        functions=functions,
        pathspecs=pathspecs,
        metadata=metadata,
    )


RULE_OBJECT_SPEC = build_rule_spec()

__all__ = ["RULE_OBJECT_SPEC"]
