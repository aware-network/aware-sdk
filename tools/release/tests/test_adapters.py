from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from aware_release.publish.adapters import (
    CommandAdapter,
    GitHubReleasesAdapter,
    NoOpAdapter,
    S3Adapter,
    build_adapter,
)
from aware_release.publish.models import PublishContext, UploadResult
from aware_release.schemas.release import BundleManifest


def _dummy_manifest(tmp_path: Path) -> BundleManifest:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        """{
            "channel": "dev",
            "version": "0.1.0",
            "built_at": "2025-10-24T00:00:00Z",
            "platform": "linux-x86_64",
            "checksum": {"sha256": "0" * 64},
            "providers": {},
            "dependencies": []
        }""".replace(
            "\"0\" * 64", "\"0000000000000000000000000000000000000000000000000000000000000000\""
        ),
        encoding="utf-8",
    )
    return BundleManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))


@pytest.fixture()
def publish_context(tmp_path: Path) -> PublishContext:
    archive = tmp_path / "bundle.tar.gz"
    archive.write_text("bundle", encoding="utf-8")
    manifest = _dummy_manifest(tmp_path)
    return PublishContext(
        manifest_path=tmp_path / "manifest.json",
        archive_path=archive,
        manifest=manifest,
        url=None,
        notes=None,
        dry_run=False,
        adapter_name="noop",
        adapter_options={},
        releases_index_path=None,
        signature_command=None,
    )


def test_noop_adapter_returns_skipped(publish_context: PublishContext) -> None:
    adapter = NoOpAdapter()
    result = adapter.publish(publish_context)
    assert result.status == "skipped"
    assert "Bundle ready" in result.logs[1]


def test_command_adapter_runs_subprocess(publish_context: PublishContext) -> None:
    adapter = CommandAdapter("echo uploaded {archive}")
    with mock.patch("subprocess.run") as run_mock:
        run_mock.return_value = mock.Mock(returncode=0, stdout="done", stderr="")
        result = adapter.publish(publish_context)
    assert result.status == "succeeded"
    assert "uploaded" in result.logs[0]


def test_github_adapter_requires_token(publish_context: PublishContext, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = GitHubReleasesAdapter(repo="aware/example", token_env="NON_EXISTENT_TOKEN")
    result = adapter.publish(publish_context)
    assert result.status == "failed"
    assert "environment variable" in result.logs[0]


def test_build_adapter_github_requires_repo() -> None:
    with pytest.raises(ValueError):
        build_adapter("github", options={})


def test_build_adapter_github_success(monkeypatch: pytest.MonkeyPatch, publish_context: PublishContext) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    adapter = build_adapter("github", options={"repo": "aware/example"})
    assert isinstance(adapter, GitHubReleasesAdapter)


def test_build_adapter_s3_requires_args() -> None:
    with pytest.raises(ValueError):
        build_adapter("s3", options={"bucket": "foo"})


def test_build_adapter_s3_success() -> None:
    adapter = build_adapter("s3", options={"bucket": "cli", "path": "cli/{channel}/{version}/{filename}"})
    assert isinstance(adapter, S3Adapter)
