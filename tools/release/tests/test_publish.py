from __future__ import annotations

from pathlib import Path

from aware_release.bundle.builder import BundleBuilder, BundleConfig
from aware_release.bundle.provider import ProviderArtifact
from aware_release.publish import PublishContext, publish_bundle
from aware_release.publish.adapters import build_adapter
from aware_release.schemas.release import BundleManifest

from .test_bundle_builder import _create_wheel


def _build_bundle(tmp_path: Path) -> tuple[Path, Path, BundleManifest]:
    wheel = tmp_path / "aware_cli-0.1.0-py3-none-any.whl"
    _create_wheel(wheel, "aware_cli", "0.1.0")
    builder = BundleBuilder()
    config = BundleConfig(
        channel="dev",
        version="0.1.0",
        platform="linux-x86_64",
        source_wheels=[wheel],
        output_dir=tmp_path / "out",
        providers={},
    )
    archive = builder.build(config)
    manifest_path = archive.parent / "manifest.json"
    manifest = BundleManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    return archive, manifest_path, manifest


def test_publish_noop_adapter(tmp_path: Path) -> None:
    archive, manifest_path, manifest = _build_bundle(tmp_path)
    context = PublishContext(
        manifest_path=manifest_path,
        archive_path=archive,
        manifest=manifest,
        url=None,
        notes=None,
        dry_run=True,
        adapter_name="noop",
        adapter_options={},
        releases_index_path=None,
        signature_command=None,
    )
    result = publish_bundle(context)
    assert result.upload.adapter == "noop"
    assert result.upload.status == "skipped"
    assert result.index_updated is False


def test_command_adapter_executes(tmp_path: Path) -> None:
    archive, manifest_path, manifest = _build_bundle(tmp_path)
    index_path = tmp_path / "releases.json"
    context = PublishContext(
        manifest_path=manifest_path,
        archive_path=archive,
        manifest=manifest,
        url="https://example.invalid/bundle.tar.gz",
        notes="demo",
        dry_run=False,
        adapter_name="command",
        adapter_options={"command": "echo upload {archive}"},
        releases_index_path=index_path,
        signature_command=None,
    )
    result = publish_bundle(context)
    assert result.upload.status == "succeeded"
    assert result.index_updated is True
    assert index_path.exists()
