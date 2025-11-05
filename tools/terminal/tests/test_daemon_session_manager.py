from __future__ import annotations

import shutil

import pytest

from aware_terminal.daemon.manifest import ManifestStore
from aware_terminal.daemon.session_manager import SessionManager, tmux_session_name
from aware_terminal.core.util import run


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux not available")
def test_session_manager_registers_session(tmp_path) -> None:
    thread = "test-daemon"
    manifest_path = tmp_path / "manifest.json"
    socket_path = tmp_path / "socket.sock"
    store = ManifestStore(manifest_path)
    manager = SessionManager(thread=thread, manifest_store=store, socket_path=socket_path)

    try:
        try:
            manifest = manager.restore_manifest()
        except RuntimeError as exc:
            if "error connecting" in str(exc):
                pytest.skip("tmux not available for automated tests")
            raise
        assert manifest.thread == thread

        record = manager.register_session(
            apt_id="apt-codex",
            session_id="sess-codex",
            shell="/bin/bash",
            cwd=tmp_path,
            start_script=None,
        )

        updated = manager.load_manifest()
        assert any(sess.session_id == record.session_id for sess in updated.sessions)

        tmux_name = tmux_session_name(thread)
        result = run(["tmux", "has-session", "-t", f"{tmux_name}:{record.tmux_window}"], check=False)
        assert result.code == 0
    finally:
        run(["tmux", "kill-session", "-t", tmux_session_name(thread)], check=False)
