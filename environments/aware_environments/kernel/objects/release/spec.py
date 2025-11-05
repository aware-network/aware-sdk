"""Release object specification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Sequence

from aware_environment import ObjectFunctionSpec, ObjectSpec, PathSpec, Visibility
from aware_environment.object.arguments import ArgumentSpec, serialize_arguments


RELEASE_ARGUMENTS: Dict[str, Sequence[ArgumentSpec]] = {
    "bundle": (
        ArgumentSpec("workspace_root", ("--workspace-root",), help="Override releases workspace root."),
        ArgumentSpec("channel", ("--channel",), help="Release channel identifier.", required=True),
        ArgumentSpec("version", ("--version",), help="Semantic version for the release.", required=True),
        ArgumentSpec("platform", ("--platform",), help="Target platform tag (e.g. linux-x86_64).", required=True),
        ArgumentSpec("wheels", ("--wheel",), help="Wheel artifact path.", required=True, multiple=True),
        ArgumentSpec("dependencies_file", ("--dependencies-file",), help="Path to dependencies.txt for manifest packaging."),
        ArgumentSpec("providers_dir", ("--providers-dir",), help="Directory containing provider metadata.", multiple=True),
        ArgumentSpec("provider_wheel", ("--provider-wheel",), help="Provider wheel artifact path.", multiple=True),
        ArgumentSpec("output_dir", ("--output-dir",), help="Bundle output directory."),
        ArgumentSpec("manifest_override", ("--manifest-override",), help="Manifest key=value override.", multiple=True),
    ),
    "manifest-validate": (
        ArgumentSpec("workspace_root", ("--workspace-root",), help="Override releases workspace root."),
        ArgumentSpec("manifest_path", ("--manifest",), help="Manifest file path.", required=True),
        ArgumentSpec("archive_path", ("--archive",), help="Bundle archive path (for checksum validation)."),
        ArgumentSpec("schema_only", ("--schema-only",), help="Skip checksum validation.", expects_value=False),
    ),
    "locks-generate": (
        ArgumentSpec("workspace_root", ("--workspace-root",), help="Override releases workspace root."),
        ArgumentSpec("platform", ("--platform",), help="Target platform identifier.", required=True),
        ArgumentSpec("requirements", ("--requirements",), help="Requirements file path.", required=True, multiple=True),
        ArgumentSpec("python_version", ("--python-version",), help="Python version constraint."),
        ArgumentSpec("output_path", ("--output",), help="Lockfile output path."),
    ),
    "publish": (
        ArgumentSpec("workspace_root", ("--workspace-root",), help="Override releases workspace root."),
        ArgumentSpec("manifest_path", ("--manifest",), help="Manifest file path.", required=True),
        ArgumentSpec("archive_path", ("--archive",), help="Bundle archive path.", required=True),
        ArgumentSpec("releases_index_path", ("--releases-json",), help="Existing releases index path."),
        ArgumentSpec("url", ("--url",), help="Published bundle URL."),
        ArgumentSpec("notes", ("--notes",), help="Release notes or changelog."),
        ArgumentSpec("adapter_name", ("--adapter",), help="Publish adapter name.", default="noop"),
        ArgumentSpec("adapter_command", ("--adapter-command",), help="Adapter command override."),
        ArgumentSpec("adapter_arg", ("--adapter-arg",), help="Adapter option key=value.", multiple=True),
        ArgumentSpec("signature_command", ("--signature-command",), help="Command to sign artifacts."),
        ArgumentSpec("actor", ("--actor",), help="Actor performing the publish."),
        ArgumentSpec("dry_run", ("--dry-run",), help="Run without performing writes.", expects_value=False, default=True),
    ),
    "terminal-refresh": (
        ArgumentSpec("workspace_root", ("--workspace-root",), help="Override releases workspace root."),
        ArgumentSpec("manifests_dir", ("--manifests-dir",), help="Directory containing aware-terminal provider manifests.", default="libs/providers/terminal/aware_terminal_providers/providers"),
    ),
    "terminal-validate": (
        ArgumentSpec("workspace_root", ("--workspace-root",), help="Override releases workspace root."),
        ArgumentSpec("manifests_dir", ("--manifests-dir",), help="Directory containing aware-terminal provider manifests.", default="libs/providers/terminal/aware_terminal_providers/providers"),
    ),
    "workflow-trigger": (
        ArgumentSpec("workspace_root", ("--workspace-root",), help="Override releases workspace root."),
        ArgumentSpec("workflow", ("--workflow",), help="Workflow slug to dispatch.", required=True),
        ArgumentSpec("ref", ("--ref",), help="Git reference to use when dispatching."),
        ArgumentSpec("inputs", ("--input",), help="Workflow input key=value.", multiple=True),
        ArgumentSpec("token_env", ("--token-env",), help="Environment variable containing the API token."),
        ArgumentSpec("dry_run", ("--dry-run",), help="Dispatch workflow without executing actions.", expects_value=False, default=False),
        ArgumentSpec("github_api", ("--github-api",), help="GitHub API base URL.", default="https://api.github.com"),
    ),
    "secrets-list": (
        ArgumentSpec("workspace_root", ("--workspace-root",), help="Override releases workspace root."),
        ArgumentSpec("name", ("--name",), help="Filter to a specific secret."),
    ),
}


def _argument_metadata(name: str) -> Sequence[Mapping[str, object]]:
    return serialize_arguments(RELEASE_ARGUMENTS.get(name, ()))


def build_release_spec() -> ObjectSpec:
    metadata = {"default_selectors": {"workspace_root": "releases", "repository_root": "."}}

    functions = (
        ObjectFunctionSpec(
            name="bundle",
            handler_factory="aware_environments.kernel.objects.release.handlers:bundle",
            metadata={
                "selectors": ("workspace_root", "repository_root"),
                "pathspecs": {
                    "reads": ["release-workspace"],
                    "creates": ["release-bundles"],
                    "updates": ["release-bundles", "release-locks"],
                },
                "arguments": _argument_metadata("bundle"),
            },
        ),
        ObjectFunctionSpec(
            name="manifest-validate",
            handler_factory="aware_environments.kernel.objects.release.handlers:manifest_validate",
            metadata={
                "selectors": ("workspace_root",),
                "pathspecs": {
                    "reads": ["release-workspace"],
                },
                "arguments": _argument_metadata("manifest-validate"),
            },
        ),
        ObjectFunctionSpec(
            name="locks-generate",
            handler_factory="aware_environments.kernel.objects.release.handlers:locks_generate",
            metadata={
                "selectors": ("workspace_root", "platform"),
                "pathspecs": {
                    "reads": ["release-workspace"],
                    "updates": ["release-locks"],
                },
                "arguments": _argument_metadata("locks-generate"),
            },
        ),
        ObjectFunctionSpec(
            name="publish",
            handler_factory="aware_environments.kernel.objects.release.handlers:publish",
            metadata={
                "selectors": ("workspace_root",),
                "pathspecs": {
                    "reads": ["release-bundles"],
                },
                "arguments": _argument_metadata("publish"),
            },
        ),
        ObjectFunctionSpec(
            name="terminal-refresh",
            handler_factory="aware_environments.kernel.objects.release.handlers:terminal_refresh",
            metadata={
                "selectors": ("workspace_root", "manifests_dir"),
                "arguments": _argument_metadata("terminal-refresh"),
            },
        ),
        ObjectFunctionSpec(
            name="terminal-validate",
            handler_factory="aware_environments.kernel.objects.release.handlers:terminal_validate",
            metadata={
                "selectors": ("workspace_root", "manifests_dir"),
                "arguments": _argument_metadata("terminal-validate"),
            },
        ),
        ObjectFunctionSpec(
            name="workflow-trigger",
            handler_factory="aware_environments.kernel.objects.release.handlers:workflow_trigger",
            metadata={
                "selectors": ("workspace_root",),
                "arguments": _argument_metadata("workflow-trigger"),
            },
        ),
        ObjectFunctionSpec(
            name="secrets-list",
            handler_factory="aware_environments.kernel.objects.release.handlers:secrets_list",
            metadata={
                "selectors": ("workspace_root",),
                "arguments": _argument_metadata("secrets-list"),
            },
        ),
    )

    pathspecs = (
        PathSpec(
            id="release-workspace",
            layout_path=("releases",),
            instantiation_path=("releases",),
            visibility=Visibility.PRIVATE,
        ),
        PathSpec(
            id="release-bundles",
            layout_path=("releases", "bundles"),
            instantiation_path=("releases", "bundles"),
            visibility=Visibility.PRIVATE,
        ),
        PathSpec(
            id="release-locks",
            layout_path=("releases", "locks"),
            instantiation_path=("releases", "locks"),
            visibility=Visibility.PRIVATE,
        ),
    )

    return ObjectSpec(
        type="release",
        description="Release bundle and publish operations.",
        metadata=metadata,
        functions=functions,
        pathspecs=pathspecs,
    )


RELEASE_OBJECT_SPEC = build_release_spec()

__all__ = ["RELEASE_OBJECT_SPEC", "RELEASE_ARGUMENTS"]
