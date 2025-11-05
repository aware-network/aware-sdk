from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .models import (
    CliPrepareResult,
    CliPublishResult,
    CliPublishUpload,
    ProviderRefreshResult,
    ProviderValidationIssue,
    ProviderValidationResult,
    RulesRenderResult,
)


def prepare_release(
    *,
    channel: str,
    version: str,
    platform: str,
    wheels: Sequence[str],
    output_dir: str | Path = "releases",
    providers_dir: Optional[Sequence[str]] = None,
    provider_wheels: Optional[Sequence[str]] = None,
    dependencies_file: Optional[str] = None,
    manifest_overrides: Optional[Sequence[str]] = None,
    generate_lockfile: bool = False,
    lock_output: Optional[str] = None,
    python_version: Optional[str] = None,
    workspace_root: str | Path = ".",
) -> CliPrepareResult:
    """Bundle wheels + manifest and optionally produce lockfiles."""

    workspace = Path(workspace_root).resolve()
    wheel_paths = [Path(w) if Path(w).is_absolute() else workspace / w for w in wheels]
    provider_candidates: List[Path] = []
    for entry in providers_dir or []:
        candidate = Path(entry)
        provider_candidates.append(candidate if candidate.is_absolute() else workspace / candidate)
    for entry in provider_wheels or []:
        candidate = Path(entry)
        provider_candidates.append(candidate if candidate.is_absolute() else workspace / candidate)

    providers, provider_artifacts = _collect_providers(provider_candidates)

    overrides = _parse_overrides(manifest_overrides)
    dependencies = _read_dependencies(workspace / dependencies_file) if dependencies_file else None

    output = Path(output_dir)
    if not output.is_absolute():
        output = workspace / output

    from aware_release.bundle.builder import BundleBuilder, BundleConfig
    from aware_release.bundle.locks import LockRequest, generate_lock
    from aware_release.bundle.manifest import load_manifest
    from aware_release.bundle.provider import discover_providers

    builder = BundleBuilder(workspace_root=workspace)
    config = BundleConfig(
        channel=channel,
        version=version,
        platform=platform,
        source_wheels=[path.resolve() for path in wheel_paths],
        output_dir=output,
        dependencies=dependencies,
        providers=providers,
        provider_artifacts=provider_artifacts,
        manifest_overrides=overrides,
    )

    archive_path = builder.build(config)
    manifest_path = archive_path.parent / "manifest.json"
    manifest = load_manifest(manifest_path)

    lock_path = None
    if generate_lockfile:
        lock_output_path = Path(lock_output) if lock_output else output / "locks" / f"{platform}.txt"
        if not lock_output_path.is_absolute():
            lock_output_path = workspace / lock_output_path
        request = LockRequest(
            requirements=manifest.dependencies,
            platform=platform,
            output_path=lock_output_path,
            python_version=python_version,
        )
        lock_path = generate_lock(request)

    return CliPrepareResult(
        archive_path=str(archive_path),
        manifest_path=str(manifest_path),
        manifest=manifest.model_dump(mode="json"),
        lock_path=str(lock_path) if lock_path else None,
    )


def render_rules(
    *,
    version: Optional[str] = None,
    rules_root: str | Path = "docs/rules",
    manifest_path: str | Path = "build/rule-manifest.json",
    update_current: str = "copy",
    workspace_root: str | Path = ".",
    clean_manifest: bool = True,
) -> RulesRenderResult:
    workspace = Path(workspace_root).resolve()

    resolved_rules_root = Path(rules_root)
    if not resolved_rules_root.is_absolute():
        resolved_rules_root = workspace / resolved_rules_root

    resolved_manifest = Path(manifest_path)
    if not resolved_manifest.is_absolute():
        resolved_manifest = workspace / resolved_manifest
    resolved_manifest.parent.mkdir(parents=True, exist_ok=True)
    if clean_manifest and resolved_manifest.exists():
        resolved_manifest.unlink()

    rule_ids = _discover_rule_ids()
    if not rule_ids:
        raise RuntimeError("No rule templates discovered via aware-cli list_rules().")

    cli_version = version or _resolve_cli_version()

    try:
        from aware_cli.cli import main as aware_cli_main
    except ImportError as exc:  # pragma: no cover - dependency declared, guard for clarity
        raise RuntimeError("aware-cli must be available to render rules.") from exc

    args: List[str] = [
        "docs",
        "render",
        "--target",
        "rules",
        "--write-version",
        "--rules-root",
        str(resolved_rules_root),
        "--update-current",
        update_current,
        "--json-output",
        str(resolved_manifest),
        "--cli-version",
        cli_version,
    ]
    for rule_id in rule_ids:
        args += ["--rule", rule_id]

    exit_code = aware_cli_main(args)
    if exit_code != 0:
        raise RuntimeError(f"aware-cli docs render exited with status {exit_code}.")

    return RulesRenderResult(
        cli_version=cli_version,
        rules_root=str(resolved_rules_root),
        manifest_path=str(resolved_manifest),
        rules=rule_ids,
        update_current=update_current,
    )


def publish_release(
    *,
    channel: str,
    version: str,
    platform: str,
    output_dir: str | Path = "releases",
    adapter: str = "noop",
    adapter_options: Optional[Dict[str, object]] = None,
    releases_index: Optional[str | Path] = None,
    url: Optional[str] = None,
    notes: Optional[str] = None,
    dry_run: bool = False,
    signature_command: Optional[str] = None,
    actor: Optional[str] = None,
    workspace_root: str | Path = ".",
) -> CliPublishResult:
    workspace = Path(workspace_root).resolve()
    output = Path(output_dir)
    if not output.is_absolute():
        output = workspace / output

    base_dir = output / channel / version / platform
    manifest_path = base_dir / "manifest.json"
    archive_name = f"aware-cli-{channel}-{version}-{platform}.tar.gz"
    archive_path = base_dir / archive_name

    from aware_release.bundle.manifest import load_manifest
    from aware_release.publish import PublishContext, publish_bundle

    manifest = load_manifest(manifest_path)

    context = PublishContext(
        manifest_path=manifest_path,
        archive_path=archive_path,
        manifest=manifest,
        url=url,
        notes=notes,
        dry_run=dry_run,
        adapter_name=adapter,
        adapter_options=adapter_options or {},
        releases_index_path=(workspace / releases_index if releases_index else output / "release-index.json"),
        signature_command=signature_command,
        actor=actor,
    )
    result = publish_bundle(context)
    upload = CliPublishUpload(
        adapter=result.upload.adapter,
        status=result.upload.status,
        url=result.upload.url,
        details=result.upload.details,
        logs=result.upload.logs,
    )
    return CliPublishResult(
        manifest_path=str(result.manifest_path),
        archive_path=str(result.archive_path),
        checksum_match=result.checksum_match,
        index_path=str(result.index_path) if result.index_path else None,
        index_updated=result.index_updated,
        signature_path=str(result.signature_path) if result.signature_path else None,
        upload=upload,
        logs=result.logs,
        next_steps=result.next_steps,
        metadata=result.metadata,
    )


def refresh_terminal_providers(
    *,
    workspace_root: str | Path = ".",
    manifests_dir: str | Path = "libs/providers/terminal/aware_terminal_providers/providers",
) -> ProviderRefreshResult:
    workspace = Path(workspace_root).resolve()
    manifests_root = Path(manifests_dir)
    if not manifests_root.is_absolute():
        manifests_root = workspace / manifests_root

    logs: List[str] = []
    manifest_paths: List[str] = []
    providers_changed: List[str] = []

    scripts_dir = workspace / "libs" / "providers" / "terminal" / "scripts"
    updater = scripts_dir / "update_provider_versions.py"
    if not updater.exists():
        raise FileNotFoundError(f"Provider updater script not found: {updater}")

    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            str(updater),
            "--write",
            "--verbose",
        ],
        cwd=str(scripts_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    logs.append(proc.stdout)
    if proc.stderr:
        logs.append(proc.stderr)
    if proc.returncode != 0:
        raise RuntimeError(f"Provider manifest refresh failed with exit code {proc.returncode}: {proc.stderr.strip()}")

    for manifest_path in manifests_root.glob("*/releases.json"):
        manifest_paths.append(str(manifest_path))
        providers_changed.append(manifest_path.parent.name)

    from datetime import datetime

    return ProviderRefreshResult(
        manifest_paths=manifest_paths,
        providers_changed=providers_changed,
        timestamp=datetime.utcnow(),
        logs=logs,
    )


def validate_terminal_providers(
    *,
    workspace_root: str | Path = ".",
    manifests_dir: str | Path = "libs/providers/terminal/aware_terminal_providers/providers",
) -> ProviderValidationResult:
    workspace = Path(workspace_root).resolve()
    manifests_root = Path(manifests_dir)
    if not manifests_root.is_absolute():
        manifests_root = workspace / manifests_root

    manifest_paths = sorted(str(path) for path in manifests_root.glob("*/releases.json"))
    issues: List[ProviderValidationIssue] = []

    import json as _json

    def _validate_versions_schema(manifest_path: Path, payload: dict, issues: List[ProviderValidationIssue]) -> None:
        versions = payload.get("versions", [])
        if not isinstance(versions, list):
            issues.append(
                ProviderValidationIssue(
                    manifest=str(manifest_path),
                    message="'versions' must be a list.",
                )
            )
            return

        seen_tags: Dict[str, str] = {}
        for entry in versions:
            if not isinstance(entry, dict):
                issues.append(
                    ProviderValidationIssue(
                        manifest=str(manifest_path),
                        message="Version entry must be an object.",
                    )
                )
                continue
            tag = entry.get("tag")
            version = entry.get("version")
            if not tag or not version:
                issues.append(
                    ProviderValidationIssue(
                        manifest=str(manifest_path),
                        message="Version entry missing 'tag' or 'version'.",
                    )
                )
                continue
            if tag in seen_tags and seen_tags[tag] != version:
                issues.append(
                    ProviderValidationIssue(
                        manifest=str(manifest_path),
                        message=f"Tag '{tag}' mapped to conflicting versions ({seen_tags[tag]} vs {version}).",
                    )
                )
            else:
                seen_tags[tag] = version

    def _validate_channels_schema(manifest_path: Path, payload: dict, issues: List[ProviderValidationIssue]) -> None:
        channels = payload.get("channels")
        if not isinstance(channels, dict) or not channels:
            issues.append(
                ProviderValidationIssue(
                    manifest=str(manifest_path),
                    message="Manifest 'channels' must be a non-empty object.",
                )
            )
            return

        for channel_name, channel_data in channels.items():
            if not isinstance(channel_data, dict):
                issues.append(
                    ProviderValidationIssue(
                        manifest=str(manifest_path),
                        message=f"Channel '{channel_name}' entry must be an object.",
                    )
                )
                continue
            version = channel_data.get("version")
            if not isinstance(version, str) or not version.strip():
                issues.append(
                    ProviderValidationIssue(
                        manifest=str(manifest_path),
                        message=f"Channel '{channel_name}' missing string 'version'.",
                    )
                )
            npm_tag = channel_data.get("npm_tag")
            if npm_tag is not None and not isinstance(npm_tag, str):
                issues.append(
                    ProviderValidationIssue(
                        manifest=str(manifest_path),
                        message=f"Channel '{channel_name}' has non-string 'npm_tag'.",
                    )
                )
            release_notes = channel_data.get("release_notes")
            if release_notes is not None and not isinstance(release_notes, dict):
                issues.append(
                    ProviderValidationIssue(
                        manifest=str(manifest_path),
                        message=f"Channel '{channel_name}' has invalid 'release_notes' type (expected object).",
                    )
                )
            if isinstance(release_notes, dict):
                summary = release_notes.get("summary")
                if summary is not None and not isinstance(summary, str):
                    issues.append(
                        ProviderValidationIssue(
                            manifest=str(manifest_path),
                            message=f"Channel '{channel_name}' release notes 'summary' must be a string if present.",
                        )
                    )

    for manifest_path_str in manifest_paths:
        manifest_path = Path(manifest_path_str)
        try:
            data = _json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - reported via validation
            issues.append(
                ProviderValidationIssue(
                    manifest=str(manifest_path),
                    message=f"Failed to parse manifest: {exc}",
                )
            )
            continue

        if not isinstance(data, dict):
            issues.append(
                ProviderValidationIssue(
                    manifest=str(manifest_path),
                    message="Manifest must be a JSON object.",
                )
            )
            continue

        if "versions" in data:
            _validate_versions_schema(manifest_path, data, issues)
        elif "channels" in data:
            _validate_channels_schema(manifest_path, data, issues)
        else:
            issues.append(
                ProviderValidationIssue(
                    manifest=str(manifest_path),
                    message="Manifest missing supported schema ('versions' or 'channels').",
                )
            )

    return ProviderValidationResult(
        manifest_paths=manifest_paths,
        issues=issues,
    )


def _collect_providers(paths: Iterable[Path]) -> tuple[Dict[str, Dict[str, object]], List]:
    from aware_release.bundle.provider import discover_providers

    artifacts = discover_providers(paths)
    providers: Dict[str, Dict[str, object]] = {}
    for artifact in artifacts:
        providers[artifact.slug] = {
            "version": artifact.version,
            "source": artifact.source.name,
            "metadata": dict(artifact.metadata),
        }
    return providers, artifacts


def _read_dependencies(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Dependencies file not found: {path}")
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _parse_overrides(values: Optional[Sequence[str]]) -> Dict[str, object]:
    overrides: Dict[str, object] = {}
    if not values:
        return overrides
    for entry in values:
        if "=" not in entry:
            raise ValueError(f"Manifest override must be key=value (got '{entry}')")
        key, raw_value = entry.split("=", 1)
        overrides[key.strip()] = raw_value.strip()
    return overrides


def _discover_rule_ids() -> List[str]:
    from aware_cli.registry.rules import list_rules

    return [rule.id for rule in list_rules()]


def _resolve_cli_version() -> str:
    try:
        from aware_cli import __version__ as cli_version
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Unable to resolve aware-cli version; pass --version explicitly.") from exc
    return cli_version


def publish_awarerelease_pypi(
    *,
    workspace_root: str | Path = ".",
    build_dir: str | Path = "dist",
    pyproject_path: str | Path = "tools/release/pyproject.toml",
    repository: str = "pypi",
    dry_run: bool = False,
) -> Dict[str, object]:
    workspace = Path(workspace_root).resolve()
    build_dir_path = Path(build_dir) if Path(build_dir).is_absolute() else workspace / build_dir
    pyproject = Path(pyproject_path)
    if not pyproject.is_absolute():
        pyproject = workspace / pyproject
    if not pyproject.exists():
        raise FileNotFoundError(f"pyproject not found: {pyproject}")

    import subprocess

    build_cmd = [
        "uv",
        "build",
        "--project",
        str(pyproject.parent),
        "--wheel",
        "--out-dir",
        str(build_dir_path),
    ]
    publish_cmd = [
        "uv",
        "publish",
        "--project",
        str(pyproject.parent),
    ]
    if repository and repository != "pypi":
        publish_cmd.extend(["--index", repository])
    if dry_run:
        publish_cmd.append("--dry-run")
    logs: List[str] = []

    build_result = subprocess.run(build_cmd, capture_output=True, text=True, check=False)
    logs.extend([build_result.stdout, build_result.stderr])
    if build_result.returncode != 0:
        raise RuntimeError(f"uv build failed: {build_result.stderr.strip()}")

    wheels = sorted(build_dir_path.glob("*.whl"))
    if not wheels:
        raise RuntimeError(f"No wheel artifacts found in {build_dir_path}")

    publish_args = publish_cmd + [str(path) for path in wheels]

    if dry_run:
        return {
            "built": sorted(str(path) for path in build_dir_path.glob("*.whl")),
            "logs": logs,
            "published": False,
        }

    publish_result = subprocess.run(publish_args, capture_output=True, text=True, check=False)
    logs.extend([publish_result.stdout, publish_result.stderr])
    if publish_result.returncode != 0:
        raise RuntimeError(f"uv publish failed: {publish_result.stderr.strip()}")

    return {
        "built": sorted(str(path) for path in build_dir_path.glob("*.whl")),
        "logs": logs,
        "published": True,
        "repository": repository,
    }
