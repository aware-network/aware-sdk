from __future__ import annotations

import zipfile
from pathlib import Path
from email.message import EmailMessage

import pytest

from aware_release.bundle.provider import ProviderArtifact, discover_providers


def test_provider_artifact_dataclass() -> None:
    artifact = ProviderArtifact(
        slug="codex",
        version="1.0.0",
        source=Path("codex.whl"),
        metadata={"scope": "test"},
    )
    assert artifact.slug == "codex"
    assert artifact.metadata["scope"] == "test"


def test_discover_providers_from_files(tmp_path: Path) -> None:
    wheel_a = tmp_path / "alpha-1.0.0-py3-none-any.whl"
    wheel_b = tmp_path / "beta-2.0.0-py3-none-any.whl"
    _create_provider_wheel(wheel_a, "alpha", "1.0.0", summary="Alpha provider", requires=["httpx>=1.0"])
    _create_provider_wheel(wheel_b, "beta", "2.0.0")

    artifacts = discover_providers([wheel_a, wheel_b])
    mapping = {artifact.slug: artifact for artifact in artifacts}
    assert set(mapping) == {"alpha", "beta"}
    assert mapping["alpha"].metadata.get("summary") == "Alpha provider"
    assert mapping["alpha"].metadata.get("requires") == ["httpx>=1.0"]


def test_discover_providers_rejects_bad_filename(tmp_path: Path) -> None:
    bad_wheel = tmp_path / "invalid.whl"
    bad_wheel.touch()
    with pytest.raises(ValueError):
        discover_providers([bad_wheel])


def _create_provider_wheel(
    path: Path,
    package: str,
    version: str,
    *,
    summary: str | None = None,
    requires: list[str] | None = None,
) -> None:
    message = EmailMessage()
    message["Metadata-Version"] = "2.1"
    message["Name"] = package
    message["Version"] = version
    if summary:
        message["Summary"] = summary
    for requirement in requires or []:
        message["Requires-Dist"] = requirement

    metadata_text = message.as_string()

    dist_info = f"{package}-{version}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{dist_info}/METADATA",
            metadata_text,
        )
        archive.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nGenerator: aware-release\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        archive.writestr(f"{dist_info}/RECORD", "")
