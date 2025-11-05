from __future__ import annotations

from pathlib import Path
import os

import pytest


def _repo_root() -> Path:
    marker = Path(__file__).resolve()
    for parent in [marker, *marker.parents]:
        if (parent / "tools").exists() or (parent / "aware_sdk").exists():
            return parent
    return marker.parents[4]


@pytest.fixture(autouse=True)
def _terminal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo_root()
    monkeypatch.setenv("AWARE_TERMINAL_DEV_ROOT", str(root))

    update_script = root / "libs" / "providers" / "terminal" / "scripts" / "update_provider_versions.py"
    stub_script = root / "tools" / "terminal" / "_ci_update_provider_versions.py"
    if "AWARE_TERMINAL_MANIFEST_UPDATE_SCRIPT" not in os.environ:
        if stub_script.exists():
            monkeypatch.setenv("AWARE_TERMINAL_MANIFEST_UPDATE_SCRIPT", str(stub_script))
        elif update_script.exists():
            monkeypatch.setenv("AWARE_TERMINAL_MANIFEST_UPDATE_SCRIPT", str(update_script))

    monkeypatch.setenv("AWARE_TERMINAL_ALLOW_MANIFEST_REFRESH", "1")
