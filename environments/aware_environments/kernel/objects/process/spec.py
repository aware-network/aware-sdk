"""Object specification for orchestrator process runtime operations."""

from __future__ import annotations

from typing import Dict, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments

PROCESS_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "list": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("status", ("--status",), help="Filter processes by status."),
    ),
    "status": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
    ),
    "threads": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
    ),
    "backlog": (
        ArgumentSpec("runtime_root", ("--runtime-root",), help="Override runtime root."),
        ArgumentSpec("process", ("--process",), help="Process slug."),
        ArgumentSpec("since", ("--since",), help="ISO timestamp filter."),
        ArgumentSpec("limit", ("--limit",), help="Maximum backlog entries.", value_type=int),
    ),
}


def _argument_metadata(name: str):
    return serialize_arguments(PROCESS_ARGUMENTS.get(name, ()))


def build_process_spec() -> ObjectSpec:
    metadata = {
        "default_selectors": {"runtime_root": "docs/runtime/process"},
    }

    functions = (
        ObjectFunctionSpec(
            name="list",
            handler_factory="aware_environments.kernel.objects.process.handlers:list_processes",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "arguments": _argument_metadata("list"),
                "pathspecs": {
                    "reads": ("process-root",),
                },
            },
        ),
        ObjectFunctionSpec(
            name="status",
            handler_factory="aware_environments.kernel.objects.process.handlers:process_status",
            metadata={
                "policy": "04-agent-01-memory-hierarchy",
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "selectors": ("process",),
                "arguments": _argument_metadata("status"),
                "pathspecs": {
                    "reads": ("process-dir", "process-json"),
                },
            },
        ),
        ObjectFunctionSpec(
            name="threads",
            handler_factory="aware_environments.kernel.objects.process.handlers:process_threads",
            metadata={
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "selectors": ("process",),
                "arguments": _argument_metadata("threads"),
                "pathspecs": {
                    "reads": ("process-threads-dir",),
                },
            },
        ),
        ObjectFunctionSpec(
            name="backlog",
            handler_factory="aware_environments.kernel.objects.process.handlers:process_backlog",
            metadata={
                "rule_ids": ("04-agent-01-memory-hierarchy", "02-agent-01-identity"),
                "selectors": ("process",),
                "arguments": _argument_metadata("backlog"),
                "pathspecs": {
                    "reads": ("process-backlog-dir",),
                },
            },
        ),
    )

    pathspecs = (
        PathSpec(
            id="process-root",
            layout_path=("docs", "runtime", "process"),
            instantiation_path=("docs", "runtime", "process"),
            visibility=Visibility.PRIVATE,
            description="Runtime processes root directory.",
            metadata={"kind": "directory"},
        ),
        PathSpec(
            id="process-dir",
            layout_path=("docs", "runtime", "process", "{process}"),
            instantiation_path=("docs", "runtime", "process", "{process}"),
            visibility=Visibility.PRIVATE,
            description="Process directory containing process.json and threads/.",
            metadata={"selectors": ("process",), "kind": "directory"},
        ),
        PathSpec(
            id="process-json",
            layout_path=("docs", "runtime", "process", "{process}", "process.json"),
            instantiation_path=("docs", "runtime", "process", "{process}", "process.json"),
            visibility=Visibility.PRIVATE,
            description="Process metadata file.",
            metadata={"selectors": ("process",)},
        ),
        PathSpec(
            id="process-threads-dir",
            layout_path=("docs", "runtime", "process", "{process}", "threads"),
            instantiation_path=("docs", "runtime", "process", "{process}", "threads"),
            visibility=Visibility.PRIVATE,
            description="Threads directory for the process.",
            metadata={"selectors": ("process",), "kind": "directory"},
        ),
        PathSpec(
            id="process-backlog-dir",
            layout_path=("docs", "runtime", "process", "{process}", "backlog"),
            instantiation_path=("docs", "runtime", "process", "{process}", "backlog"),
            visibility=Visibility.PRIVATE,
            description="Backlog markdown entries for the process.",
            metadata={"selectors": ("process",), "kind": "directory"},
        ),
    )

    return ObjectSpec(
        type="process",
        description="Process runtime metadata under docs/runtime/process.",
        functions=functions,
        pathspecs=pathspecs,
        metadata=metadata,
    )


PROCESS_OBJECT_SPEC = build_process_spec()

__all__ = ["PROCESS_OBJECT_SPEC"]
