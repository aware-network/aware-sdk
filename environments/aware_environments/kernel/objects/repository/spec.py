"""Repository object specification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments


REPOSITORY_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "list": (
        ArgumentSpec("repository_root", ("--repository-root",), help="Repository root (default: current directory)."),
    ),
    "index-refresh": (
        ArgumentSpec("repository_root", ("--repository-root",), help="Repository root to index.", required=True),
        ArgumentSpec("additional_paths", ("--path",), help="Additional repository paths to include.", multiple=True),
    ),
    "status": (
        ArgumentSpec("repository_root", ("--repository-root",), help="Repository root to inspect.", required=True),
    ),
}


def _argument_metadata(name: str) -> Sequence[Mapping[str, object]]:
    return serialize_arguments(REPOSITORY_ARGUMENTS.get(name, ()))


def build_repository_spec() -> ObjectSpec:
    metadata = {"default_selectors": {"repository_root": "."}}

    functions = (
        ObjectFunctionSpec(
            name="list",
            handler_factory="aware_environments.kernel.objects.repository.handlers:list_repositories",
            metadata={
                "rule_ids": ("02-agent-01-identity",),
                "selectors": ("repository_root",),
                "pathspecs": {"reads": ["repository-index-file"]},
                "arguments": _argument_metadata("list"),
            },
        ),
        ObjectFunctionSpec(
            name="index-refresh",
            handler_factory="aware_environments.kernel.objects.repository.handlers:repository_index_refresh",
            metadata={
                "rule_ids": ("02-agent-01-identity",),
                "selectors": ("repository_root",),
                "pathspecs": {
                    "reads": ["repository-root"],
                    "creates": ["repository-index-dir"],
                    "updates": ["repository-index-file"],
                },
                "arguments": _argument_metadata("index-refresh"),
            },
        ),
        ObjectFunctionSpec(
            name="status",
            handler_factory="aware_environments.kernel.objects.repository.handlers:repository_status",
            metadata={
                "rule_ids": ("02-agent-01-identity",),
                "selectors": ("repository_root",),
                "pathspecs": {
                    "reads": ["repository-index-file"],
                },
                "arguments": _argument_metadata("status"),
            },
        ),
    )

    pathspecs = (
        PathSpec(
            id="repository-root",
            layout_path=("{repository}",),
            instantiation_path=("{repository}",),
            visibility=Visibility.PRIVATE,
            description="Repository workspace root.",
            metadata={"selectors": ("repository",), "kind": "directory"},
        ),
        PathSpec(
            id="repository-aware-dir",
            layout_path=("{repository}", ".aware"),
            instantiation_path=("{repository}", ".aware"),
            visibility=Visibility.PRIVATE,
            description="Aware metadata directory.",
            metadata={"selectors": ("repository",), "kind": "directory"},
        ),
        PathSpec(
            id="repository-index-dir",
            layout_path=("{repository}", ".aware", "index"),
            instantiation_path=("{repository}", ".aware", "index"),
            visibility=Visibility.PRIVATE,
            description="Repository index directory.",
            metadata={"selectors": ("repository",), "kind": "directory"},
        ),
        PathSpec(
            id="repository-index-file",
            layout_path=("{repository}", ".aware", "index", "repository_index.json"),
            instantiation_path=("{repository}", ".aware", "index", "repository_index.json"),
            visibility=Visibility.PRIVATE,
            description="Repository index JSON.",
            metadata={"selectors": ("repository",)},
        ),
    )

    return ObjectSpec(
        type="repository",
        description="Repository metadata and index management (.aware/index).",
        metadata=metadata,
        functions=functions,
        pathspecs=pathspecs,
    )


REPOSITORY_OBJECT_SPEC = build_repository_spec()

__all__ = ["REPOSITORY_OBJECT_SPEC", "REPOSITORY_ARGUMENTS"]
