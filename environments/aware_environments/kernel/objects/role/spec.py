"""Object specification for role registry operations."""

from __future__ import annotations

from typing import Dict, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments

ROLE_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "list": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("registry_path", ("--registry-path",), help="Explicit path to role registry."),
    ),
    "policies": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("registry_path", ("--registry-path",), help="Explicit path to role registry."),
        ArgumentSpec("role", (), help="Role identifier."),
        ArgumentSpec(
            "include_cli",
            ("--include-cli",),
            help="Include CLI object metadata in the result.",
            expects_value=False,
            default=False,
        ),
    ),
    "agents": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("registry_path", ("--registry-path",), help="Explicit path to role registry."),
        ArgumentSpec("role", (), help="Role identifier."),
    ),
    "export": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("registry_path", ("--registry-path",), help="Explicit path to role registry."),
        ArgumentSpec("output_path", ("--output",), help="Optional output path for exported registry."),
    ),
    "import": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("registry_path", ("--registry-path",), help="Explicit path to role registry."),
        ArgumentSpec("payload", ("--payload",), help="Inline JSON payload."),
        ArgumentSpec("payload_file", ("--payload-file", "--input"), help="Path to JSON payload file."),
        ArgumentSpec(
            "mode",
            ("--mode",),
            help="Import mode: replace or merge.",
            default="replace",
        ),
        ArgumentSpec(
            "generated_at",
            ("--generated-at",),
            help="Override generated_at timestamp for imported registry.",
        ),
    ),
    "set-policy": (
        ArgumentSpec("identities_root", ("--identities-root",), help="Override identities root."),
        ArgumentSpec("registry_path", ("--registry-path",), help="Explicit path to role registry."),
        ArgumentSpec("role", (), help="Role identifier."),
        ArgumentSpec("payload", ("--payload",), help="Inline JSON policy payload."),
        ArgumentSpec("payload_file", ("--payload-file", "--input"), help="Path to JSON policy payload."),
        ArgumentSpec(
            "mode",
            ("--mode",),
            help="Update mode: merge or replace.",
            default="merge",
        ),
        ArgumentSpec(
            "generated_at",
            ("--generated-at",),
            help="Override generated_at timestamp for updated registry.",
        ),
    ),
}


def _argument_metadata(name: str):
    return serialize_arguments(ROLE_ARGUMENTS.get(name, ()))


def build_role_spec() -> ObjectSpec:
    metadata = {"default_selectors": {"identities_root": "docs/identities"}}

    functions = (
        ObjectFunctionSpec(
            name="list",
            handler_factory="aware_environments.kernel.objects.role.handlers:list_roles",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "arguments": _argument_metadata("list"),
                "pathspecs": {
                    "reads": ("role-registry",),
                },
            },
        ),
        ObjectFunctionSpec(
            name="policies",
            handler_factory="aware_environments.kernel.objects.role.handlers:policies_handler",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "selectors": ("role",),
                "arguments": _argument_metadata("policies"),
                "pathspecs": {
                    "reads": ("role-registry",),
                },
            },
        ),
        ObjectFunctionSpec(
            name="agents",
            handler_factory="aware_environments.kernel.objects.role.handlers:agents_handler",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "selectors": ("role",),
                "arguments": _argument_metadata("agents"),
                "pathspecs": {
                    "reads": ("role-registry",),
                },
            },
        ),
        ObjectFunctionSpec(
            name="export",
            handler_factory="aware_environments.kernel.objects.role.handlers:export_handler",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "selectors": ("registry",),
                "arguments": _argument_metadata("export"),
                "pathspecs": {
                    "reads": ("role-registry",),
                },
            },
        ),
        ObjectFunctionSpec(
            name="import",
            handler_factory="aware_environments.kernel.objects.role.handlers:import_handler",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "selectors": ("registry",),
                "arguments": _argument_metadata("import"),
                "pathspecs": {
                    "updates": ("role-registry",),
                },
            },
        ),
        ObjectFunctionSpec(
            name="set-policy",
            handler_factory="aware_environments.kernel.objects.role.handlers:set_policy_handler",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "selectors": ("role",),
                "arguments": _argument_metadata("set-policy"),
                "pathspecs": {
                    "updates": ("role-registry",),
                },
            },
        ),
    )

    pathspecs = (
        PathSpec(
            id="role-registry",
            layout_path=("docs", "identities", "_registry", "role_registry.json"),
            instantiation_path=("_registry", "role_registry.json"),
            visibility=Visibility.PRIVATE,
            description="Role registry manifest.",
            metadata={"kind": "file"},
        ),
    )

    return ObjectSpec(
        type="role",
        description="Role registry inspection and mutation.",
        functions=functions,
        pathspecs=pathspecs,
        metadata=metadata,
    )


ROLE_OBJECT_SPEC = build_role_spec()

__all__ = ["ROLE_OBJECT_SPEC"]
