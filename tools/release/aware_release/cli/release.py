"""Command-line helpers for release automation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence

from aware_release.bundle.builder import BundleBuilder, BundleConfig
from aware_release.bundle.locks import LockRequest, generate_lock
from aware_release.bundle.manifest import load_manifest
from aware_release.bundle.provider import ProviderArtifact, discover_providers
from aware_release.bundle.utils import compute_sha256
from aware_release.publish import PublishContext, publish_bundle


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "bundle":
        return _handle_bundle(args)
    if args.command == "manifest":
        if args.manifest_command == "validate":
            return _handle_manifest_validate(args)
        parser.error("manifest command requires a subcommand")
    if args.command == "locks":
        if args.locks_command == "generate":
            return _handle_locks_generate(args)
        parser.error("locks command requires a subcommand")
    if args.command == "publish":
        return _handle_publish(args)

    parser.error(f"Unknown command '{args.command}'")
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aware-release", description="Release tooling helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bundle = subparsers.add_parser("bundle", help="Build aware-cli bundle archives.")
    bundle.add_argument("--channel", required=True)
    bundle.add_argument("--version", required=True)
    bundle.add_argument("--platform", required=True)
    bundle.add_argument("--wheel", action="append", required=True, help="Wheel path (repeatable).")
    bundle.add_argument("--dependencies-file")
    bundle.add_argument("--providers-dir", action="append")
    bundle.add_argument("--provider-wheel", action="append")
    bundle.add_argument("--output-dir")
    bundle.add_argument("--manifest-override", action="append", help="Manifest overrides key=value.")
    bundle.add_argument("--workspace-root")

    manifest = subparsers.add_parser("manifest", help="Manifest utilities.")
    manifest_sub = manifest.add_subparsers(dest="manifest_command", required=True)
    manifest_validate = manifest_sub.add_parser("validate", help="Validate bundle manifest.")
    manifest_validate.add_argument("--manifest", required=True)
    manifest_validate.add_argument("--archive")
    manifest_validate.add_argument("--schema-only", action="store_true")
    manifest_validate.add_argument("--workspace-root")

    locks = subparsers.add_parser("locks", help="Lockfile helpers.")
    locks_sub = locks.add_subparsers(dest="locks_command", required=True)
    locks_generate = locks_sub.add_parser("generate", help="Generate dependency lockfile.")
    locks_generate.add_argument("--platform", required=True)
    locks_generate.add_argument("--requirements", action="append", required=True)
    locks_generate.add_argument("--output")
    locks_generate.add_argument("--python-version")
    locks_generate.add_argument("--workspace-root")

    publish = subparsers.add_parser("publish", help="Validate and publish bundle metadata.")
    publish.add_argument("--manifest", required=True)
    publish.add_argument("--archive", required=True)
    publish.add_argument("--releases-json")
    publish.add_argument("--url")
    publish.add_argument("--notes")
    publish.add_argument("--adapter", default="noop")
    publish.add_argument("--adapter-command")
    publish.add_argument("--adapter-arg", action="append")
    publish.add_argument("--signature-command")
    publish.add_argument("--actor")
    publish.add_argument("--workspace-root")
    publish.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)

    return parser


def _handle_bundle(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace_root)
    wheels = [_resolve_path(path, workspace) for path in args.wheel]
    dependencies = _read_dependencies(_resolve_optional_path(args.dependencies_file, workspace))

    provider_candidates: List[Path] = []
    for value in args.providers_dir or []:
        provider_candidates.append(_resolve_path(value, workspace))
    for value in args.provider_wheel or []:
        provider_candidates.append(_resolve_path(value, workspace))

    provider_map, provider_artifacts = _collect_providers(provider_candidates)

    overrides = _parse_overrides(args.manifest_override)

    output_dir = (
        _resolve_path(args.output_dir, workspace)
        if args.output_dir
        else workspace / "releases"
    )

    builder = BundleBuilder(workspace_root=workspace)
    config = BundleConfig(
        channel=args.channel,
        version=args.version,
        platform=args.platform,
        source_wheels=wheels,
        output_dir=output_dir,
        dependencies=dependencies,
        providers=provider_map,
        provider_artifacts=provider_artifacts,
        manifest_overrides=overrides,
    )

    archive_path = builder.build(config)
    manifest_path = archive_path.parent / "manifest.json"
    manifest = load_manifest(manifest_path)

    payload = {
        "archive_path": str(archive_path),
        "manifest_path": str(manifest_path),
        "checksum": {"sha256": manifest.checksum.sha256},
        "manifest": manifest.model_dump(mode="json"),
        "logs": [
            f"Archive written to {archive_path}",
            f"Manifest written to {manifest_path}",
        ],
    }
    _print_json(payload)
    return 0


def _handle_manifest_validate(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace_root)
    manifest_path = _resolve_path(args.manifest, workspace)
    archive_path = _resolve_optional_path(args.archive, workspace)

    errors: List[str] = []
    manifest = _load_manifest_safe(manifest_path, errors)
    valid = manifest is not None and not errors

    checksum_match: Optional[bool] = None
    if valid and archive_path and not args.schema_only:
        if not archive_path.exists():
            errors.append(f"Archive not found: {archive_path}")
            valid = False
        else:
            checksum = compute_sha256(archive_path)
            checksum_match = checksum == manifest.checksum.sha256
            if not checksum_match:
                errors.append(
                    f"Checksum mismatch. Manifest={manifest.checksum.sha256} Archive={checksum}"
                )
                valid = False

    payload = {
        "manifest_path": str(manifest_path),
        "archive_path": str(archive_path) if archive_path else None,
        "valid": valid,
        "checksum_match": checksum_match,
        "errors": errors,
        "manifest": manifest.model_dump(mode="json") if manifest else None,
    }
    _print_json(payload)
    return 0


def _handle_locks_generate(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace_root)
    requirement_paths = [_resolve_path(path, workspace) for path in args.requirements]
    requirements = _read_requirements(requirement_paths)

    output_path = (
        _resolve_path(args.output, workspace)
        if args.output
        else workspace / "releases" / "locks" / f"{args.platform}.txt"
    )

    request = LockRequest(
        requirements=requirements,
        platform=args.platform,
        output_path=output_path,
        python_version=args.python_version,
    )
    generated = generate_lock(request)
    payload = {
        "path": str(generated),
        "platform": args.platform,
        "python_version": args.python_version,
        "requirements": requirements,
    }
    _print_json(payload)
    return 0


def _handle_publish(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args.workspace_root)
    manifest_path = _resolve_path(args.manifest, workspace)
    archive_path = _resolve_path(args.archive, workspace)
    manifest = load_manifest(manifest_path)

    adapter_options = _parse_adapter_args(args.adapter_arg or [])
    if args.adapter_command:
        adapter_options["command"] = args.adapter_command

    context = PublishContext(
        manifest_path=manifest_path,
        archive_path=archive_path,
        manifest=manifest,
        url=args.url,
        notes=args.notes,
        dry_run=args.dry_run,
        adapter_name=args.adapter,
        adapter_options=adapter_options,
        releases_index_path=_resolve_optional_path(args.releases_json, workspace),
        signature_command=args.signature_command,
        actor=args.actor,
    )
    result = publish_bundle(context)
    payload = {
        "manifest_path": str(result.manifest_path),
        "archive_path": str(result.archive_path),
        "checksum_match": result.checksum_match,
        "index_path": str(result.index_path) if result.index_path else None,
        "index_updated": result.index_updated,
        "signature_path": str(result.signature_path) if result.signature_path else None,
        "upload": {
            "adapter": result.upload.adapter,
            "status": result.upload.status,
            "url": result.upload.url,
            "details": result.upload.details,
            "logs": result.upload.logs,
        },
        "logs": result.logs,
        "next_steps": result.next_steps,
        "metadata": result.metadata,
    }
    _print_json(payload)
    return 0


def _resolve_workspace(value: Optional[str]) -> Path:
    return Path(value).resolve() if value else Path.cwd()


def _resolve_path(value: str, workspace: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = workspace / path
    return path.resolve()


def _resolve_optional_path(value: Optional[str], workspace: Path) -> Optional[Path]:
    if value is None:
        return None
    return _resolve_path(value, workspace)


def _parse_overrides(values: Optional[Sequence[str]]) -> Mapping[str, object]:
    overrides: dict[str, object] = {}
    if not values:
        return overrides
    for entry in values:
        if "=" not in entry:
            raise ValueError(f"Manifest override must be key=value (got '{entry}')")
        key, raw_value = entry.split("=", 1)
        overrides[key.strip()] = _coerce_override_value(raw_value.strip())
    return overrides


def _coerce_override_value(value: str) -> object:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    for caster in (int, float):
        try:
            return caster(value)
        except ValueError:
            continue
    return value


def _read_dependencies(path: Optional[Path]) -> Optional[List[str]]:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"Dependencies file not found: {path}")
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _read_requirements(paths: Sequence[Path]) -> List[str]:
    requirements: List[str] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Requirements file not found: {path}")
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            requirements.append(stripped)
    return requirements


def _collect_providers(candidate_paths: Iterable[Path]) -> tuple[Mapping[str, Mapping[str, object]], List[ProviderArtifact]]:
    providers: dict[str, Mapping[str, object]] = {}
    artifacts = discover_providers(candidate_paths)
    for artifact in artifacts:
        providers[artifact.slug] = {
            "version": artifact.version,
            "source": artifact.source.name,
            "metadata": dict(artifact.metadata),
        }
    return providers, artifacts


def _load_manifest_safe(path: Path, errors: List[str]) -> Optional[BundleManifest]:
    try:
        return load_manifest(path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        errors.append(str(exc))
        return None


def _parse_adapter_args(values: Sequence[str]) -> dict[str, object]:
    options: dict[str, object] = {}
    for entry in values:
        if "=" not in entry:
            raise ValueError(f"Adapter argument must be key=value (got '{entry}')")
        key, raw_value = entry.split("=", 1)
        options[key.strip()] = raw_value.strip()
    return options


def _print_json(payload: Mapping[str, object]) -> None:
    print(json.dumps(payload, indent=2, default=str))
