from __future__ import annotations

from pathlib import Path

import pytest

from aware_terminal.daemon.client import TerminalDaemonClient
from aware_terminal.daemon.manifest import ManifestStore
from aware_terminal.daemon.models import Manifest, SessionRecord


def _build_manifest(thread: str, socket_path: Path, working_dir: Path) -> Manifest:
    record = SessionRecord(
        apt_id="apt-1",
        session_id="apt-1",
        tmux_window="apt-apt-1",
        shell="/bin/bash",
        cwd=working_dir,
    )
    return Manifest(thread=thread, socket_path=socket_path, sessions=[record])


def test_client_manifest_fallback(tmp_path) -> None:
    thread = "thread-1"
    socket_path = tmp_path / "sock"
    manifest_path = tmp_path / "manifest.json"
    store = ManifestStore(manifest_path)
    manifest = _build_manifest(thread, socket_path, tmp_path)
    store.write(manifest)

    client = TerminalDaemonClient(socket_path=socket_path, manifest_store=store)
    sessions = client.list_sessions()
    assert sessions and sessions[0].session_id == "apt-1"


def test_client_raises_without_daemon(tmp_path) -> None:
    thread = "thread-1"
    socket_path = tmp_path / "sock"
    manifest_path = tmp_path / "manifest.json"
    store = ManifestStore(manifest_path)
    manifest = _build_manifest(thread, socket_path, tmp_path)
    store.write(manifest)

    client = TerminalDaemonClient(socket_path=socket_path, manifest_store=store)
    with pytest.raises(FileNotFoundError):
        client.attach("apt-1", 80, 24)
