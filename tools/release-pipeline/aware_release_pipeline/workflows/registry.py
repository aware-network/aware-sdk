from __future__ import annotations

from typing import Dict, Iterable

from aware_release.workflows import WorkflowInputSpec, WorkflowSpec

DEFAULT_REPO = "aware-network/aware"

PROVIDER_GH_TOKEN = "GH_TOKEN_PROVIDERS"

WORKFLOWS: Dict[str, WorkflowSpec] = {
    "tests-release": WorkflowSpec(
        slug="tests-release",
        repo=DEFAULT_REPO,
        workflow="publish-aware-test-runner.yml",
        description="Publish aware-test-runner package (GitHub + PyPI).",
        inputs={
            "version": WorkflowInputSpec(description="Version to publish", required=True),
            "dry_run": WorkflowInputSpec(description="Dry run flag (true/false)", default="true"),
            "timestamp": WorkflowInputSpec(description="Release timestamp"),
        },
    ),
    "cli-release": WorkflowSpec(
        slug="cli-release",
        repo=DEFAULT_REPO,
        workflow="release-cli.yml",
        description="Build and publish aware-cli bundles via the release pipeline.",
        inputs={
            "channel": WorkflowInputSpec(description="Release channel", default="dev", required=True),
            "version": WorkflowInputSpec(description="CLI version", required=True),
            "platform": WorkflowInputSpec(description="Target platform", default="linux-x86_64"),
        },
    ),
    "cli-rules-version": WorkflowSpec(
        slug="cli-rules-version",
        repo=DEFAULT_REPO,
        workflow="cli-rules-version.yml",
        description="Regenerate rule documents and manifest via aware-cli.",
        inputs={
            "version": WorkflowInputSpec(description="Optional CLI version override"),
        },
    ),
    "file-system-release": WorkflowSpec(
        slug="file-system-release",
        repo=DEFAULT_REPO,
        workflow="publish-aware-file-system.yml",
        description="Publish aware-file-system package (GitHub + PyPI).",
        inputs={
            "version": WorkflowInputSpec(description="Version to publish", required=True),
            "dry_run": WorkflowInputSpec(description="Dry run flag (true/false)", default="true"),
            "timestamp": WorkflowInputSpec(description="Release timestamp"),
        },
    ),
    "environment-release": WorkflowSpec(
        slug="environment-release",
        repo=DEFAULT_REPO,
        workflow="publish-aware-environment.yml",
        description="Publish aware-environment package (GitHub + PyPI).",
        inputs={
            "version": WorkflowInputSpec(description="Version to publish", required=True),
            "dry_run": WorkflowInputSpec(description="Dry run flag (true/false)", default="true"),
            "timestamp": WorkflowInputSpec(description="Release timestamp"),
        },
    ),
    "aware-release": WorkflowSpec(
        slug="aware-release",
        repo=DEFAULT_REPO,
        workflow="publish-aware-release.yml",
        description="Build and publish aware-release package via trusted publishing.",
        inputs={
            "repository": WorkflowInputSpec(description="PyPI repository", default="pypi"),
            "dry_run": WorkflowInputSpec(description="Dry run flag (true/false)", default="false"),
        },
    ),
    "sdk-release": WorkflowSpec(
        slug="sdk-release",
        repo=DEFAULT_REPO,
        workflow="publish-aware-sdk.yml",
        description="Publish aware-sdk bundle (GitHub + PyPI).",
        inputs={
            "version": WorkflowInputSpec(description="Version to publish", required=True),
            "dry_run": WorkflowInputSpec(description="Dry run flag (true/false)", default="true"),
            "timestamp": WorkflowInputSpec(description="Release timestamp"),
        },
    ),
    "terminal-release": WorkflowSpec(
        slug="terminal-release",
        repo=DEFAULT_REPO,
        workflow="publish-aware-terminal.yml",
        description="Publish aware-terminal package (GitHub + PyPI).",
        inputs={
            "version": WorkflowInputSpec(description="Version to publish", required=True),
            "dry_run": WorkflowInputSpec(description="Dry run flag (true/false)", default="true"),
            "timestamp": WorkflowInputSpec(description="Release timestamp"),
        },
    ),
    "terminal-providers-release": WorkflowSpec(
        slug="terminal-providers-release",
        repo=DEFAULT_REPO,
        workflow="publish-aware-terminal-providers.yml",
        description="Publish aware-terminal-providers package (GitHub + PyPI).",
        inputs={
            "version": WorkflowInputSpec(description="Version to publish", required=True),
            "dry_run": WorkflowInputSpec(description="Dry run flag (true/false)", default="true"),
            "timestamp": WorkflowInputSpec(description="Release timestamp"),
        },
    ),
    "update-providers": WorkflowSpec(
        slug="update-providers",
        repo=DEFAULT_REPO,
        workflow="update-providers.yml",
        description="Refresh terminal provider manifests and open PRs with updates.",
        dry_run_supported=False,
        token_env=PROVIDER_GH_TOKEN,
    ),
}


def get_workflow(slug: str) -> WorkflowSpec:
    try:
        return WORKFLOWS[slug].model_copy()
    except KeyError as exc:  # pragma: no cover - exercised via CLI error handling
        available = ", ".join(sorted(WORKFLOWS))
        raise KeyError(f"Unknown workflow slug '{slug}'. Available workflows: {available}.") from exc


def list_workflows() -> Iterable[WorkflowSpec]:
    for spec in WORKFLOWS.values():
        yield spec.model_copy()
