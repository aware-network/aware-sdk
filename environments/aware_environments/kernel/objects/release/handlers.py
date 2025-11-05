"""Kernel handlers for release object operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from aware_environment.fs import (
    EnsureInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)
from aware_release.bundle.manifest import load_manifest
from aware_release.bundle.utils import compute_sha256
from aware_release.secrets import describe_secret, list_secrets
from aware_release.workflows import trigger_workflow as dispatch_workflow
from aware_release_pipeline.models import ProviderRefreshResult, ProviderValidationResult
from aware_release_pipeline.pipeline import refresh_terminal_providers, validate_terminal_providers
from aware_release_pipeline.workflows import get_workflow

from .models import (
    ReleaseBundleArtifact,
    ReleaseLockArtifact,
    ReleaseManifestModel,
    ReleaseManifestValidation,
    ReleasePublishOutcome,
)
from .write_plan import (
    ReleaseBundlePlanResult,
    ReleaseLockPlanResult,
    ReleasePublishPlanResult,
    plan_bundle,
    plan_generate_lock,
    plan_publish,
)


@dataclass(frozen=True)
class ReleaseTerminalRefreshPlanResult:
    """Plan result emitted after refreshing terminal provider manifests."""

    plan: OperationPlan
    payload: Dict[str, object]


_DEFAULT_MANIFESTS_DIR = Path("libs/providers/terminal/aware_terminal_providers/providers")


def _resolve_workspace_root(value: Path | str | None) -> Path:
    if value is None:
        return Path(".").resolve()
    root = Path(value)
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def _resolve_path(value: Path | str, workspace_root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = workspace_root / path
    return path.resolve()


def _parse_key_value_pairs(values: Optional[Sequence[str]]) -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    for entry in values or ():
        if "=" not in entry:
            raise ValueError(f"Input must be key=value (got '{entry}')")
        key, raw_value = entry.split("=", 1)
        pairs[key.strip()] = raw_value.strip()
    return pairs


def _iso_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_path_sequence(values: Sequence[Path | str], workspace_root: Path) -> List[Path]:
    paths: List[Path] = []
    for value in values or ():
        path = _resolve_path(value, workspace_root)
        paths.append(path)
    return paths


def _collect_dependencies_from_file(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Dependencies file not found: {path}")
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#"):
            lines.append(entry)
    return lines


def _parse_manifest_overrides(values: Optional[Sequence[str]]) -> Dict[str, object]:
    overrides: Dict[str, object] = {}
    for entry in values or ():
        if "=" not in entry:
            raise ValueError(f"Manifest override must be key=value (got '{entry}')")
        key, raw_value = entry.split("=", 1)
        overrides[key.strip()] = raw_value.strip()
    return overrides


def _load_requirements_files(paths: Sequence[Path]) -> List[str]:
    requirements: List[str] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Requirements file not found: {path}")
        for line in path.read_text(encoding="utf-8").splitlines():
            entry = line.strip()
            if entry and not entry.startswith("#"):
                requirements.append(entry)
    return requirements


def bundle(
    workspace_root: Path | str,
    *,
    channel: str,
    version: str,
    platform: str,
    wheels: Sequence[Path | str],
    dependencies: Optional[Sequence[str]] = None,
    dependencies_file: Optional[Path | str] = None,
    providers_dir: Sequence[Path | str] = (),
    provider_wheel: Sequence[Path | str] = (),
    provider_paths: Sequence[Path | str] = (),
    manifest_overrides: Optional[Mapping[str, object]] = None,
    manifest_override: Optional[Sequence[str]] = None,
    output_dir: Optional[Path | str] = None,
) -> ReleaseBundlePlanResult:
    workspace = _resolve_workspace_root(workspace_root)

    resolved_wheels = _normalise_path_sequence(wheels, workspace)

    resolved_dependencies = list(dependencies or ())
    if dependencies_file is not None:
        dependency_path = _resolve_path(dependencies_file, workspace)
        resolved_dependencies = _collect_dependencies_from_file(dependency_path)

    provider_candidates: List[Path] = []
    provider_candidates.extend(_normalise_path_sequence(provider_paths, workspace))
    provider_candidates.extend(_normalise_path_sequence(providers_dir, workspace))
    provider_candidates.extend(_normalise_path_sequence(provider_wheel, workspace))

    overrides = dict(manifest_overrides or {})
    if manifest_override:
        overrides.update(_parse_manifest_overrides(manifest_override))

    resolved_output = _resolve_path(output_dir, workspace) if output_dir else None

    return plan_bundle(
        workspace,
        channel=channel,
        version=version,
        platform=platform,
        wheels=tuple(resolved_wheels),
        dependencies=resolved_dependencies or None,
        provider_paths=tuple(provider_candidates),
        manifest_overrides=overrides or None,
        output_dir=resolved_output,
    )


def locks_generate(
    workspace_root: Path | str,
    *,
    platform: str,
    requirements: Sequence[str],
    python_version: str | None = None,
    output_path: Path | str | None = None,
) -> ReleaseLockPlanResult:
    workspace = _resolve_workspace_root(workspace_root)
    requirement_paths = [_resolve_path(path, workspace) for path in requirements]
    resolved_requirements = _load_requirements_files(requirement_paths)
    resolved_output = _resolve_path(output_path, workspace) if output_path else None

    return plan_generate_lock(
        workspace,
        platform=platform,
        requirements=resolved_requirements,
        python_version=python_version,
        output_path=resolved_output,
    )


def publish(
    workspace_root: Path | str,
    *,
    manifest_path: Path | str,
    archive_path: Path | str,
    manifest=None,
    url: Optional[str],
    notes: Optional[str],
    dry_run: bool,
    adapter_name: str,
    adapter_options: Optional[Mapping[str, object]] = None,
    adapter_arg: Optional[Sequence[str]] = None,
    adapter_command: Optional[str] = None,
    releases_index_path: Optional[Path | str] = None,
    signature_command: Optional[str] = None,
    actor: Optional[str] = None,
) -> ReleasePublishPlanResult:
    workspace = _resolve_workspace_root(workspace_root)
    manifest_path = _resolve_path(manifest_path, workspace)
    archive_path = _resolve_path(archive_path, workspace)

    manifest_obj = manifest
    if manifest_obj is None or not hasattr(manifest_obj, "checksum"):
        manifest_obj = load_manifest(manifest_path)

    options: Dict[str, object] = dict(adapter_options or {})
    if adapter_arg:
        options.update(_parse_key_value_pairs(adapter_arg))
    if adapter_command:
        options["command"] = adapter_command

    releases_index = _resolve_path(releases_index_path, workspace) if releases_index_path else None

    return plan_publish(
        workspace,
        manifest_path=manifest_path,
        archive_path=archive_path,
        manifest=manifest_obj,
        url=url,
        notes=notes,
        dry_run=dry_run,
        adapter_name=adapter_name,
        adapter_options=options,
        releases_index_path=releases_index,
        signature_command=signature_command,
        actor=actor,
    )


def manifest_validate(
    workspace_root: Path | str,
    *,
    manifest_path: Path | str,
    archive_path: Path | str | None = None,
    schema_only: bool = False,
) -> ReleaseManifestValidation:
    workspace = _resolve_workspace_root(workspace_root)
    manifest_path = _resolve_path(manifest_path, workspace)
    archive_path = _resolve_path(archive_path, workspace) if archive_path is not None else None

    errors: List[str] = []
    manifest_obj = None
    manifest_model: Optional[ReleaseManifestModel] = None
    try:
        manifest_obj = load_manifest(manifest_path)
        manifest_model = ReleaseManifestModel.from_release(manifest_obj)
        valid = True
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        errors.append(str(exc))
        valid = False

    checksum_match: Optional[bool] = None
    if valid and archive_path is not None and not schema_only:
        if not archive_path.exists():
            errors.append(f"Archive not found: {archive_path}")
            valid = False
        else:
            archive_checksum = compute_sha256(archive_path)
            checksum_match = manifest_obj.checksum.sha256 == archive_checksum if manifest_obj else None
            if manifest_obj and checksum_match is False:
                errors.append(
                    f"Checksum mismatch. Manifest={manifest_obj.checksum.sha256} Archive={archive_checksum}"
                )
                valid = False

    return ReleaseManifestValidation(
        manifest_path=manifest_path,
        valid=valid,
        checksum_match=checksum_match,
        errors=errors,
        manifest=manifest_model,
    )


def terminal_refresh(
    workspace_root: Path | str,
    *,
    manifests_dir: Path | str | None = None,
) -> ReleaseTerminalRefreshPlanResult:
    workspace = _resolve_workspace_root(workspace_root)
    manifests_root = Path(manifests_dir) if manifests_dir is not None else _DEFAULT_MANIFESTS_DIR
    if not manifests_root.is_absolute():
        manifests_root = workspace / manifests_root
    manifests_root = manifests_root.resolve()
    manifests_root.mkdir(parents=True, exist_ok=True)

    existing_paths = {str(path.resolve()) for path in manifests_root.glob("*/releases.json")}

    refresh_result: ProviderRefreshResult = refresh_terminal_providers(
        workspace_root=str(workspace),
        manifests_dir=str(manifests_root),
    )

    timestamp = _iso_now()
    ensure_map: Dict[Path, EnsureInstruction] = {}
    writes: List[WriteInstruction] = []

    for manifest_path_str in refresh_result.manifest_paths:
        manifest_path = Path(manifest_path_str)
        if not manifest_path.is_absolute():
            manifest_path = manifests_root / manifest_path
        manifest_path = manifest_path.resolve()
        ensure_map.setdefault(manifest_path.parent, EnsureInstruction(path=manifest_path.parent))
        if not manifest_path.exists():
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text("{}", encoding="utf-8")
        content = manifest_path.read_text(encoding="utf-8")
        event = "modified" if str(manifest_path) in existing_paths else "created"
        metadata = {
            "provider": manifest_path.parent.name,
            "manifests_dir": str(manifests_root),
        }
        writes.append(
            WriteInstruction(
                path=manifest_path,
                content=content,
                policy=OperationWritePolicy.MODIFIABLE,
                event=event,
                doc_type="terminal-provider-manifest",
                timestamp=timestamp,
                metadata=metadata,
            )
        )

    context = OperationContext(
        object_type="release",
        function="terminal-refresh",
        selectors={
            "workspace_root": str(workspace),
            "manifests_dir": str(manifests_dir if manifests_dir is not None else _DEFAULT_MANIFESTS_DIR),
        },
    )

    plan = OperationPlan(
        context=context,
        ensure_dirs=tuple(ensure_map.values()),
        writes=tuple(writes),
    )

    payload = refresh_result.to_dict()
    return ReleaseTerminalRefreshPlanResult(plan=plan, payload=payload)


def terminal_validate(
    workspace_root: Path | str,
    *,
    manifests_dir: Path | str | None = None,
) -> Dict[str, object]:
    workspace = _resolve_workspace_root(workspace_root)
    manifests_root = Path(manifests_dir) if manifests_dir is not None else _DEFAULT_MANIFESTS_DIR
    if not manifests_root.is_absolute():
        manifests_root = workspace / manifests_root
    manifests_root = manifests_root.resolve()

    validation_result: ProviderValidationResult = validate_terminal_providers(
        workspace_root=str(workspace),
        manifests_dir=str(manifests_root),
    )
    return validation_result.to_dict()


def workflow_trigger(
    *,
    workflow: str,
    inputs: Optional[Sequence[str]] = None,
    ref: Optional[str] = None,
    token_env: Optional[str] = None,
    dry_run: bool = False,
    github_api: Optional[str] = None,
) -> Dict[str, object]:
    spec = get_workflow(workflow)
    parsed_inputs = _parse_key_value_pairs(inputs)
    result = dispatch_workflow(
        spec,
        ref=ref,
        inputs=parsed_inputs or None,
        token_env_override=token_env,
        dry_run=dry_run,
        github_api=(github_api or "https://api.github.com"),
    )
    return result.model_dump(mode="json")


def secrets_list(*, workspace_root: Path | str | None = None, name: Optional[str] = None) -> List[Dict[str, object]]:
    secrets = sorted(list_secrets(), key=lambda spec: spec.name)
    if name:
        secrets = [spec for spec in secrets if spec.name == name]
    return [describe_secret(spec.name) for spec in secrets]


__all__ = [
    "bundle",
    "publish",
    "locks_generate",
    "manifest_validate",
    "terminal_refresh",
    "terminal_validate",
    "workflow_trigger",
    "secrets_list",
    "ReleaseBundleArtifact",
    "ReleasePublishOutcome",
    "ReleaseLockArtifact",
    "ReleaseLockPlanResult",
    "ReleaseBundlePlanResult",
    "ReleasePublishPlanResult",
    "ReleaseTerminalRefreshPlanResult",
]
