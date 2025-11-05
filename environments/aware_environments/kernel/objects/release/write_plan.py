"""OperationPlan builders for release object workflows."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence
from uuid import uuid4

from aware_environment.fs import (
    EnsureInstruction,
    MoveInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)
from aware_release.bundle.locks import _resolve_with_uv
from aware_release.bundle.builder import BundleBuilder, BundleConfig
from aware_release.bundle.manifest import load_manifest
from aware_release.bundle.provider import ProviderArtifact, discover_providers
from aware_release.bundle.utils import compute_sha256
from aware_release.publish.adapters import build_adapter
from aware_release.publish.index import load_release_index, update_release_index
from aware_release.publish.models import PublishContext, UploadResult
from aware_release.schemas.release import BundleManifest

from .models import (
    ReleaseBundleArtifact,
    ReleaseJournalEntry,
    ReleaseLockArtifact,
    ReleasePublishOutcome,
    ReleaseUploadSummary,
)


def _iso_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_requirements(requirements: Sequence[str]) -> list[str]:
    return [entry.strip() for entry in requirements if entry and entry.strip()]


def _default_lock_path(workspace_root: Path, platform: str) -> Path:
    return Path(workspace_root) / "releases" / "locks" / f"{platform}.txt"


@dataclass(frozen=True)
class ReleaseLockPlanResult:
    plan: OperationPlan
    artifact: ReleaseLockArtifact


@dataclass(frozen=True)
class ReleaseBundlePlanResult:
    plan: OperationPlan
    artifact: ReleaseBundleArtifact
    staging_root: Path


@dataclass(frozen=True)
class ReleasePublishPlanResult:
    plan: OperationPlan
    outcome: ReleasePublishOutcome
    staging_paths: tuple[Path, ...] = ()


def plan_generate_lock(
    workspace_root: Path,
    *,
    platform: str,
    requirements: Sequence[str],
    python_version: Optional[str],
    output_path: Optional[Path],
) -> ReleaseLockPlanResult:
    workspace = Path(workspace_root)
    target_path = Path(output_path) if output_path is not None else _default_lock_path(workspace, platform)
    normalised_requirements = _normalise_requirements(requirements)

    resolved = _resolve_with_uv(normalised_requirements, python_version, platform)

    header_lines = [
        "# aware-release lockfile",
        f"# platform: {platform}",
    ]
    if python_version:
        header_lines.append(f"# python: {python_version}")
    header_lines.append("# generated via `uv pip compile --quiet`")

    lines = [*header_lines, ""]
    lines.extend(resolved)
    if lines[-1] != "":
        lines.append("")
    content = "\n".join(lines)

    now = _iso_now()
    selectors = {
        "workspace": str(workspace.resolve()),
        "platform": platform,
    }
    context = OperationContext(object_type="release", function="locks-generate", selectors=selectors)

    event = "modified" if target_path.exists() else "created"
    metadata = {"platform": platform, "workspace": str(workspace)}
    if python_version:
        metadata["python_version"] = python_version

    plan = OperationPlan(
        context=context,
        ensure_dirs=(EnsureInstruction(path=target_path.parent),),
        writes=(
            WriteInstruction(
                path=target_path,
                content=content,
                policy=OperationWritePolicy.MODIFIABLE,
                event=event,
                doc_type="release-lock",
                timestamp=now,
                metadata=metadata,
            ),
        ),
    )

    try:
        relative_path = target_path.relative_to(workspace)
    except ValueError:
        relative_path = target_path

    artifact = ReleaseLockArtifact(
        path=relative_path,
        platform=platform,
        python_version=python_version,
        requirements=resolved or normalised_requirements,
        generated_at=now,
    )

    return ReleaseLockPlanResult(plan=plan, artifact=artifact)


def _relative_to_workspace(workspace: Path, path: Path) -> Path:
    try:
        return path.relative_to(workspace)
    except ValueError:
        return path


def _providers_metadata(artifacts: Sequence[ProviderArtifact]) -> dict[str, Mapping[str, object]]:
    providers: dict[str, Mapping[str, object]] = {}
    for artifact in artifacts:
        providers[artifact.slug] = {
            "version": artifact.version,
            "source": artifact.source.name,
            "metadata": dict(artifact.metadata),
        }
    return providers


def plan_bundle(
    workspace_root: Path,
    *,
    channel: str,
    version: str,
    platform: str,
    wheels: Sequence[Path],
    dependencies: Optional[Sequence[str]],
    provider_paths: Sequence[Path],
    manifest_overrides: Optional[Mapping[str, object]],
    output_dir: Optional[Path],
) -> ReleaseBundlePlanResult:
    workspace = Path(workspace_root)
    staging_root = workspace / ".aware" / "staging" / f"bundle-{uuid4().hex}"
    artifact_output_root = staging_root / "output"
    artifact_output_root.mkdir(parents=True, exist_ok=True)

    provider_artifacts = discover_providers(provider_paths)
    providers_map = _providers_metadata(provider_artifacts) if provider_artifacts else None

    builder = BundleBuilder(workspace_root=workspace)
    config = BundleConfig(
        channel=channel,
        version=version,
        platform=platform,
        source_wheels=[Path(path) for path in wheels],
        output_dir=artifact_output_root,
        dependencies=list(dependencies or ()),
        providers=providers_map,
        provider_artifacts=provider_artifacts,
        manifest_overrides=dict(manifest_overrides or {}),
    )
    archive_stage_path = builder.build(config)
    manifest_stage_path = archive_stage_path.parent / "manifest.json"

    target_base = Path(output_dir) if output_dir is not None else workspace / "releases"
    target_dir = target_base / channel / version / platform
    archive_target_path = target_dir / archive_stage_path.name
    manifest_target_path = target_dir / "manifest.json"

    now = _iso_now()
    selectors = {
        "workspace": str(workspace.resolve()),
        "channel": channel,
        "version": version,
        "platform": platform,
    }
    context = OperationContext(object_type="release", function="bundle", selectors=selectors)

    plan = OperationPlan(
        context=context,
        ensure_dirs=(EnsureInstruction(path=target_dir),),
        moves=(
            MoveInstruction(src=archive_stage_path, dest=archive_target_path, overwrite=True),
            MoveInstruction(src=manifest_stage_path, dest=manifest_target_path, overwrite=True),
        ),
    )

    manifest = load_manifest(manifest_stage_path)
    checksum = compute_sha256(archive_stage_path)
    artifact = ReleaseBundleArtifact(
        archive_path=_relative_to_workspace(workspace, archive_target_path),
        manifest_path=_relative_to_workspace(workspace, manifest_target_path),
        channel=channel,
        version=version,
        platform=platform,
        checksum=checksum,
        dependencies=list(manifest.dependencies or []),
        providers=[artifact.slug for artifact in provider_artifacts],
        built_at=manifest.built_at or now,
    )

    return ReleaseBundlePlanResult(plan=plan, artifact=artifact, staging_root=staging_root)


def _build_upload_summary(result: UploadResult) -> ReleaseUploadSummary:
    return ReleaseUploadSummary(
        adapter=result.adapter,
        status=result.status,
        url=result.url,
        details=dict(result.details),
        logs=list(result.logs),
    )


def plan_publish(
    workspace_root: Path,
    *,
    manifest_path: Path,
    archive_path: Path,
    manifest,
    url: Optional[str],
    notes: Optional[str],
    dry_run: bool,
    adapter_name: str,
    adapter_options: Mapping[str, object],
    releases_index_path: Optional[Path],
    signature_command: Optional[str],
    actor: Optional[str],
) -> ReleasePublishPlanResult:
    workspace = Path(workspace_root)
    manifest_path = Path(manifest_path)
    archive_path = Path(archive_path)

    checksum = compute_sha256(archive_path)
    if checksum != manifest.checksum.sha256:
        raise ValueError(
            f"Archive checksum mismatch. Manifest={manifest.checksum.sha256} Archive={checksum}"
        )

    context = PublishContext(
        manifest_path=manifest_path,
        archive_path=archive_path,
        manifest=manifest,
        url=url,
        notes=notes,
        dry_run=dry_run,
        adapter_name=adapter_name,
        adapter_options=dict(adapter_options),
        releases_index_path=releases_index_path,
        signature_command=signature_command,
        actor=actor,
    )

    adapter = build_adapter(
        context.adapter_name,
        command=context.adapter_options.get("command"),
        env={
            key[len("env.") :]: value
            for key, value in context.adapter_options.items()
            if key.startswith("env.")
        },
        options=context.adapter_options,
    )

    upload_result = UploadResult(
        adapter=adapter.name,
        status="skipped" if context.dry_run else "succeeded",
        url=context.url,
        details={},
        logs=[],
    )

    logs: list[str] = []
    journal: list[ReleaseJournalEntry] = []
    staging_paths: list[Path] = []
    signature_stage_path: Optional[Path] = None
    signature_final_path: Optional[Path] = None

    if context.dry_run:
        upload_result.logs.append("Dry run enabled; upload skipped.")
        logs.extend(upload_result.logs)
        journal.append(
            ReleaseJournalEntry(
                action="upload",
                status="skipped",
                timestamp=_iso_now(),
                metadata={
                    "adapter": adapter.name,
                    "url": context.url,
                },
            )
        )
    else:
        upload_result = adapter.publish(context)
        logs.extend(upload_result.logs)
        journal.append(
            ReleaseJournalEntry(
                action="upload",
                status=upload_result.status,
                timestamp=_iso_now(),
                metadata={
                    "adapter": adapter.name,
                    "url": context.url,
                },
            )
        )

    if context.signature_command and not context.dry_run:
        signature_candidate = archive_path.with_suffix(archive_path.suffix + ".sig")
        signature_candidate.unlink(missing_ok=True)
        from aware_release.publish.publish import _run_signature_command

        signature_path = _run_signature_command(context.signature_command, archive_path, logs)
        if signature_path is not None and signature_path.exists():
            staging_root = workspace / ".aware" / "staging" / f"publish-{uuid4().hex}"
            staging_root.mkdir(parents=True, exist_ok=True)
            staging_paths.append(staging_root)
            signature_stage_path = staging_root / signature_path.name
            signature_stage_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(signature_path, signature_stage_path)
            signature_final_path = signature_path
            journal.append(
                ReleaseJournalEntry(
                    action="signature",
                    status="generated",
                    timestamp=_iso_now(),
                    metadata={
                        "command": context.signature_command,
                        "path": str(signature_final_path),
                    },
                )
            )

    index_instruction = None
    index_path = context.releases_index_path
    index_updated = False
    if index_path and not context.dry_run:
        index = load_release_index(index_path)
        index = update_release_index(index, manifest, context.url, context.notes, signature_final_path)
        index_content = index.model_dump_json(indent=2) + "\n"
        index_instruction = WriteInstruction(
            path=index_path,
            content=index_content,
            policy=OperationWritePolicy.MODIFIABLE,
            event="modified" if index_path.exists() else "created",
            doc_type="release-index",
            timestamp=_iso_now(),
            metadata={"workspace": str(workspace), "channel": manifest.channel, "version": manifest.version},
        )
        index_updated = True
        journal.append(
            ReleaseJournalEntry(
                action="index-update",
                status="updated",
                timestamp=_iso_now(),
                metadata={
                    "path": str(index_path),
                },
            )
        )
    
    ensure_instructions = []
    move_instructions = []
    write_instructions = []

    if signature_stage_path and signature_final_path:
        ensure_instructions.append(EnsureInstruction(path=signature_final_path.parent))
        move_instructions.append(
            MoveInstruction(src=signature_stage_path, dest=signature_final_path, overwrite=True)
        )

    if index_instruction is not None:
        ensure_instructions.append(EnsureInstruction(path=index_instruction.path.parent))
        write_instructions.append(index_instruction)

    selectors = {
        "workspace": str(workspace.resolve()),
        "channel": manifest.channel,
        "version": manifest.version,
        "platform": manifest.platform,
    }
    plan_context = OperationContext(object_type="release", function="publish", selectors=selectors)

    plan = OperationPlan(
        context=plan_context,
        ensure_dirs=tuple(ensure_instructions),
        moves=tuple(move_instructions),
        writes=tuple(write_instructions),
    )

    outcome = ReleasePublishOutcome(
        manifest_path=_relative_to_workspace(workspace, manifest_path),
        archive_path=_relative_to_workspace(workspace, archive_path),
        checksum_match=True,
        index_path=_relative_to_workspace(workspace, index_path) if index_path else None,
        index_updated=index_updated,
        signature_path=_relative_to_workspace(workspace, signature_final_path) if signature_final_path else None,
        upload=_build_upload_summary(upload_result),
        logs=list(logs),
        next_steps=[],
        metadata={
            "published_at": context.published_at.isoformat() + "Z",
            **({"actor": actor} if actor else {}),
        },
        journal=journal,
    )

    if upload_result.status != "succeeded":
        outcome.next_steps.append("Upload bundle to distribution storage.")
    if index_path and not index_updated:
        outcome.next_steps.append(f"Update {index_path} with release entry once upload completes.")

    return ReleasePublishPlanResult(plan=plan, outcome=outcome, staging_paths=tuple(staging_paths))


__all__ = [
    "ReleaseBundlePlanResult",
    "plan_bundle",
    "ReleaseLockPlanResult",
    "plan_generate_lock",
]
