from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from aware_terminal.providers.manifest import (
    manifests_available,
    provider_manifests_root,
    provider_update_script,
)
from aware_terminal.remediation.manifest import ProviderManifestRefresher


@pytest.fixture(autouse=True)
def _clear_caches():
    provider_manifests_root.cache_clear()
    provider_update_script.cache_clear()
    yield
    provider_manifests_root.cache_clear()
    provider_update_script.cache_clear()


@pytest.fixture()
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dev_root = tmp_path / "sandbox"
    manifests_dir = dev_root / "libs" / "providers" / "terminal" / "aware_terminal_providers" / "providers"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    update_stub = dev_root / "update_stub.py"
    update_stub.write_text("print('stub')\n", encoding="utf-8")

    monkeypatch.setenv("AWARE_TERMINAL_DEV_ROOT", str(dev_root))
    monkeypatch.setenv("AWARE_TERMINAL_MANIFEST_ROOT", str(manifests_dir))
    monkeypatch.setenv("AWARE_TERMINAL_MANIFEST_UPDATE_SCRIPT", str(update_stub))
    monkeypatch.setenv("AWARE_TERMINAL_ALLOW_MANIFEST_REFRESH", "1")

    return manifests_dir


def _write_manifest(root: Path, slug: str, updated_at: str | None) -> None:
    payload = {
        "provider": slug,
        "channels": {
            "latest": {
                "version": "1.0.0",
                "npm_tag": "latest",
                **({"updated_at": updated_at} if updated_at else {}),
            }
        },
    }
    slug_dir = root / slug
    slug_dir.mkdir(parents=True, exist_ok=True)
    (slug_dir / "releases.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_override_manifest_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    override = tmp_path / "providers"
    override.mkdir(parents=True)
    monkeypatch.setenv("AWARE_TERMINAL_MANIFEST_ROOT", str(override))
    monkeypatch.delenv("AWARE_TERMINAL_DEV_ROOT", raising=False)
    assert provider_manifests_root() == override
    assert manifests_available()


def test_update_script_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = tmp_path / "update.py"
    script.write_text("print('noop')\n", encoding="utf-8")
    monkeypatch.setenv("AWARE_TERMINAL_MANIFEST_UPDATE_SCRIPT", str(script))
    monkeypatch.delenv("AWARE_TERMINAL_DEV_ROOT", raising=False)
    assert provider_update_script() == script


def test_dev_root_detection(sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWARE_TERMINAL_MANIFEST_ROOT", raising=False)
    monkeypatch.delenv("AWARE_TERMINAL_MANIFEST_UPDATE_SCRIPT", raising=False)
    root = provider_manifests_root()
    assert root == sandbox


def test_manifest_refresher_fresh(sandbox: Path) -> None:
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _write_manifest(sandbox, "codex", now_iso)
    refresher = ProviderManifestRefresher(providers_root=sandbox)
    status = refresher.ensure_fresh(max_age=timedelta(days=1), allow_refresh=False)
    assert status.status in {"fresh", "bundled"}


def test_manifest_refresher_stale_no_refresh(sandbox: Path) -> None:
    _write_manifest(sandbox, "codex", "2020-01-01T00:00:00Z")
    refresher = ProviderManifestRefresher(providers_root=sandbox, script_path=None)
    status = refresher.ensure_fresh(max_age=timedelta(days=1), allow_refresh=False)
    assert status.status == "stale"


def test_manifest_refresher_refresh(sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_manifest(sandbox, "codex", "2020-01-01T00:00:00Z")
    refresher = ProviderManifestRefresher(providers_root=sandbox)

    def fake_refresh(self: ProviderManifestRefresher) -> bool:  # type: ignore[override]
        _write_manifest(sandbox, "codex", "2025-10-25T01:00:00Z")
        return True

    monkeypatch.setattr(ProviderManifestRefresher, "_refresh", fake_refresh, raising=False)
    status = refresher.ensure_fresh(max_age=timedelta(hours=1), allow_refresh=True)
    assert status.status in {"refreshed", "fresh"}
