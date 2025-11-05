from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from aware_terminal.daemon.models import Manifest, SessionRecord


def test_session_record_serialisation_roundtrip() -> None:
    created = datetime(2025, 10, 20, 18, 0, tzinfo=timezone.utc)
    record = SessionRecord(
        apt_id="apt-1",
        session_id="sess-1",
        tmux_window="apt::apt-1",
        shell="/bin/bash",
        cwd=Path("/home/test"),
        created_at=created,
        last_active_at=created,
        start_script="echo hi",
    )

    data = record.as_dict()
    assert data["aptId"] == "apt-1"
    assert data["tmuxWindow"] == "apt::apt-1"
    rebuilt = SessionRecord.model_validate(data)
    assert rebuilt.apt_id == "apt-1"
    assert rebuilt.cwd == Path("/home/test")
    assert rebuilt.created_at == created


def test_manifest_roundtrip(tmp_path) -> None:
    manifest = Manifest(
        thread="thread-xyz",
        socket_path=tmp_path / "sock",
        sessions=[
            SessionRecord(
                apt_id="apt-1",
                session_id="sess-1",
                tmux_window="apt::apt-1",
                shell="/bin/bash",
                cwd=tmp_path,
            )
        ],
    )

    payload = manifest.as_dict()
    rebuilt = Manifest.model_validate(payload)
    assert rebuilt.thread == "thread-xyz"
    assert rebuilt.socket_path == tmp_path / "sock"
    assert rebuilt.sessions[0].session_id == "sess-1"
