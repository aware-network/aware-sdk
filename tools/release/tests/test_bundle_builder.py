from __future__ import annotations

import json
import tarfile
import zipfile
from pathlib import Path

from aware_release.bundle.builder import BundleBuilder, BundleConfig
from aware_release.bundle.utils import compute_sha256
from aware_release.bundle.provider import ProviderArtifact


def _create_wheel(
    path: Path,
    package: str,
    version: str,
    *,
    requires: list[str] | None = None,
    summary: str | None = None,
) -> None:
    dist_info = f"{package}-{version}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{package}/__init__.py", "__version__ = '{version}'\n")
        metadata_lines = [
            "Metadata-Version: 2.1",
            f"Name: {package}",
            f"Version: {version}",
        ]
        if summary:
            metadata_lines.append(f"Summary: {summary}")
        for requirement in requires or []:
            metadata_lines.append(f"Requires-Dist: {requirement}")
        metadata_text = "\n".join(metadata_lines) + "\n"
        archive.writestr(
            f"{dist_info}/METADATA",
            metadata_text,
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: aware-release\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr(f"{dist_info}/RECORD", "")


def test_bundle_builder_creates_archive(tmp_path: Path) -> None:
    wheel = tmp_path / "aware_cli-0.1.0-py3-none-any.whl"
    provider_wheel = tmp_path / "provider-1.0.0-py3-none-any.whl"
    _create_wheel(
        wheel,
        "aware_cli",
        "0.1.0",
        requires=["requests>=2.0"],
        summary="Aware CLI core.",
    )
    _create_wheel(
        provider_wheel,
        "provider_pkg",
        "1.0.0",
        summary="Test provider.",
    )

    output_dir = tmp_path / "out"
    builder = BundleBuilder()
    config = BundleConfig(
        channel="dev",
        version="0.0.1",
        platform="linux-x86_64",
        source_wheels=[wheel],
        output_dir=output_dir,
        dependencies=["aware-cli==0.1.0"],
        providers={
            "provider": {
                "version": "1.0.0",
                "source": "provider-1.0.0-py3-none-any.whl",
                "metadata": {"summary": "Test provider."},
            }
        },
        provider_artifacts=[
            ProviderArtifact(
                slug="provider",
                version="1.0.0",
                source=provider_wheel,
                metadata={},
            )
        ],
    )
    archive_path = builder.build(config)

    assert archive_path.exists()
    manifest_path = archive_path.parent / "manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["dependencies"] == ["aware-cli==0.1.0"]
    assert manifest["checksum"]["sha256"] == compute_sha256(archive_path)
    assert manifest["python"]
    provider_meta = manifest["providers"]["provider"]["metadata"]
    assert provider_meta["summary"] == "Test provider."

    with tarfile.open(archive_path, "r:gz") as bundle:
        names = {name.lstrip("./") for name in bundle.getnames()}
        assert "lib/aware_cli/__init__.py" in names
        assert "bin/aware-cli" in names
        assert "manifest.json" in names
        assert "providers/provider-1.0.0-py3-none-any.whl" in names
