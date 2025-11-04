"""Bundle assembly orchestration."""

from __future__ import annotations

import platform
import shutil
import stat
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Sequence

from ..schemas.release import BundleManifest
from .dependencies import collect_dependencies
from .manifest import dump_manifest
from .provider import ProviderArtifact
from .utils import compute_sha256, write_text


@dataclass(slots=True)
class BundleConfig:
    """Configuration describing one bundle run."""

    channel: str
    version: str
    platform: str
    source_wheels: Sequence[Path]
    output_dir: Path
    built_at: Optional[datetime] = None
    dependencies: Optional[Sequence[str]] = None
    providers: Optional[Mapping[str, Mapping[str, object]]] = None
    provider_artifacts: Optional[Sequence[ProviderArtifact]] = None
    manifest_overrides: Optional[Mapping[str, object]] = None


class BundleBuilder:
    """Coordinates bundle staging and archive creation."""

    def __init__(self, *, workspace_root: Optional[Path] = None) -> None:
        self.workspace_root = workspace_root or Path.cwd()

    def build(self, config: BundleConfig) -> Path:
        """Build bundle artifacts and return the archive path."""

        wheels = [Path(path) for path in config.source_wheels]
        providers = list(config.provider_artifacts or [])
        for wheel in wheels:
            if not wheel.exists():
                raise FileNotFoundError(f"Wheel not found: {wheel}")
        for artifact in providers:
            if not artifact.source.exists():
                raise FileNotFoundError(f"Provider wheel not found: {artifact.source}")

        artifact_dir = (
            config.output_dir
            / config.channel
            / config.version
            / config.platform
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)

        archive_basename = artifact_dir / f"aware-cli-{config.channel}-{config.version}-{config.platform}"
        manifest_path = artifact_dir / "manifest.json"

        with tempfile.TemporaryDirectory(prefix="aware-release-") as tmp_dir:
            staging_root = Path(tmp_dir)
            bin_dir = staging_root / "bin"
            lib_dir = staging_root / "lib"
            wheels_dir = lib_dir / "wheels"
            providers_dir = staging_root / "providers"
            bin_dir.mkdir(parents=True, exist_ok=True)
            lib_dir.mkdir(parents=True, exist_ok=True)
            wheels_dir.mkdir(parents=True, exist_ok=True)

            self._write_launch_scripts(bin_dir)

            for wheel in wheels:
                target_wheel = wheels_dir / wheel.name
                shutil.copy2(wheel, target_wheel)
                if zipfile.is_zipfile(wheel):
                    with zipfile.ZipFile(wheel) as archive:
                        archive.extractall(lib_dir)
                else:
                    shutil.copy2(wheel, lib_dir / wheel.name)

            if providers:
                providers_dir.mkdir(parents=True, exist_ok=True)
                for artifact in providers:
                    shutil.copy2(artifact.source, providers_dir / artifact.source.name)

            dependencies = list(config.dependencies or [])
            if not dependencies:
                dependencies = collect_dependencies(wheels)

            # Seed manifest with placeholder checksum; final checksum written post-archive.
            built_at = config.built_at or datetime.now(timezone.utc)
            manifest_payload = {
                "channel": config.channel,
                "version": config.version,
                "built_at": built_at,
                "platform": config.platform,
                "checksum": {"sha256": "0" * 64},
                "providers": config.providers or {},
                "dependencies": dependencies,
                "python": platform.python_version(),
            }
            if config.manifest_overrides:
                manifest_payload.update(config.manifest_overrides)

            manifest = BundleManifest.model_validate(manifest_payload)
            staging_manifest_path = staging_root / "manifest.json"
            dump_manifest(manifest, staging_manifest_path)

            archive_path = artifact_dir / f"{archive_basename.name}.tar.gz"
            with tarfile.open(archive_path, "w:gz") as bundle:
                for staging_path in sorted(
                    staging_root.rglob("*"),
                    key=lambda path: path.relative_to(staging_root).as_posix(),
                ):
                    arcname = staging_path.relative_to(staging_root).as_posix()
                    bundle.add(staging_path, arcname=arcname)

        sha = compute_sha256(archive_path)
        finalized_manifest = manifest.model_copy(
            update={
                "checksum": manifest.checksum.model_copy(update={"sha256": sha}),
                "built_at": manifest.built_at,
            }
        )
        dump_manifest(finalized_manifest, manifest_path)

        return archive_path

    def _write_launch_scripts(self, bin_dir: Path) -> None:
        script_path = bin_dir / "aware-cli"
        script_content = """#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
export PYTHONPATH="${DIR}/lib${PYTHONPATH:+:$PYTHONPATH}"
exec "${PYTHON:-python3}" -m aware_cli.cli "$@"
"""
        write_text(script_path, script_content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        cmd_path = bin_dir / "aware-cli.cmd"
        cmd_content = r"""@echo off
setlocal enabledelayedexpansion
set DIR=%~dp0..
set PYTHONPATH=%DIR%\lib;%PYTHONPATH%
if not defined PYTHON set PYTHON=python
"%PYTHON%" -m aware_cli.cli %*
"""
        write_text(cmd_path, cmd_content, newline="\r\n")
