from __future__ import annotations

import json
from pathlib import Path

from aware_release.bundle.manifest import dump_manifest, load_manifest
from aware_release.schemas.release import BundleManifest


def test_manifest_fixture_valid() -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample_manifest.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    manifest = BundleManifest.model_validate(data)
    assert manifest.channel == "dev"
    assert manifest.checksum.sha256.startswith("012345")


def test_dump_and_load_manifest_roundtrip(tmp_path: Path) -> None:
    manifest = BundleManifest(
        channel="stable",
        version="0.15.0",
        built_at="2025-10-24T18:00:00Z",
        platform="linux-x86_64",
        checksum={"sha256": "f" * 64},
        providers={},
        dependencies=["aware-cli==0.15.0"],
        python="3.12.1",
    )
    path = tmp_path / "manifest.json"
    dump_manifest(manifest, path)
    loaded = load_manifest(path)
    assert loaded.model_dump() == manifest.model_dump()
