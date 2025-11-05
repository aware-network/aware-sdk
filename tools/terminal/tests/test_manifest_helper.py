from __future__ import annotations

import os
from datetime import timedelta, datetime, timezone
from pathlib import Path

import pytest

from aware_terminal.providers.manifest import (
    provider_manifests_root,
    provider_update_script,
    manifests_available,
)
from aware_terminal.remediation.manifest import ProviderManifestRefresher


def setup_module():
    provider_manifests_root.cache_clear()
    provider_update_script.cache_clear()


def teardown_function(_):
    provider_manifests_root.cache_clear()
    provider_update_script.cache_clear()
    os.environ.pop("AWARE_TERMINAL_MANIFEST_ROOT", None)
    os.environ.pop("AWARE_TERMINAL_MANIFEST_UPDATE_SCRIPT", None)
    os.environ.pop("AWARE_TERMINAL_DEV_ROOT", None)


def test_override_manifest_root(tmp_path, monkeypatch):
    override = tmp_path / "providers"
    override.mkdir(parents=True)
    monkeypatch.setenv("AWARE_TERMINAL_MANIFEST_ROOT", str(override))
    root = provider_manifests_root()
    assert root == override
    assert manifests_available()


def test_update_script_env_override(tmp_path, monkeypatch):
    script = tmp_path / "update.py"
    script.write_text("print('noop')\n")
    monkeypatch.setenv("AWARE_TERMINAL_MANIFEST_UPDATE_SCRIPT", str(script))
    path = provider_update_script()
    assert path == script


def test_dev_root_detection(tmp_path, monkeypatch):
    libs_dir = tmp_path / "libs" / "providers" / "terminal"
    package_dir = libs_dir / "aware_terminal_providers"
    (package_dir / "providers").mkdir(parents=True)
    (package_dir / "__init__.py").write_text("__all__ = []\n")
    monkeypatch.setenv("AWARE_TERMINAL_DEV_ROOT", str(tmp_path))
    root = provider_manifests_root()
    assert root == package_dir / "providers"


def _write_manifest(root: Path, slug: str, updated_at: str | None) -> None:
    channel = {"version": "1.0.0", "npm_tag": "latest"}
    if updated_at:
        channel["updated_at"] = updated_at
    payload = {"provider": slug, "channels": {"latest": channel}}
    slug_dir = root / slug
    slug_dir.mkdir(parents=True, exist_ok=True)
    (slug_dir / "releases.json").write_text(
        __import__("json").dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def test_manifest_refresher_fresh(tmp_path):
    manifests = tmp_path / "providers"
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _write_manifest(manifests, "codex", now_iso)
    refresher = ProviderManifestRefresher(providers_root=manifests)
    status = refresher.ensure_fresh(max_age=timedelta(days=1), allow_refresh=False)
    assert status.status in {"fresh", "bundled"}


def test_manifest_refresher_stale_no_refresh(tmp_path):
    manifests = tmp_path / "providers"
    _write_manifest(manifests, "codex", "2020-01-01T00:00:00Z")
    refresher = ProviderManifestRefresher(providers_root=manifests, script_path=None)
    status = refresher.ensure_fresh(max_age=timedelta(days=1), allow_refresh=False)
    assert status.status == "stale"


def test_manifest_refresher_refresh(monkeypatch, tmp_path):
    manifests = tmp_path / "providers"
    _write_manifest(manifests, "codex", "2020-01-01T00:00:00Z")
    refresher = ProviderManifestRefresher(providers_root=manifests)

    def fake_refresh(self):
        _write_manifest(manifests, "codex", "2025-10-25T01:00:00Z")
        return True

    monkeypatch.setattr(ProviderManifestRefresher, "_refresh", fake_refresh, raising=False)
    status = refresher.ensure_fresh(max_age=timedelta(hours=1), allow_refresh=True)
    assert status.status in {"refreshed", "fresh"}
