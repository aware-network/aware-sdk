from __future__ import annotations

import tempfile
import time
import uuid
from pathlib import Path

import pytest

from aware_terminal.daemon.client import TerminalDaemonClient
from aware_terminal.daemon.manifest import ManifestStore
from aware_terminal.daemon.models import Manifest, SessionRecord
from aware_terminal.daemon.server import DaemonServer


class FakeSessionManager:
    def __init__(self, store: ManifestStore, record: SessionRecord) -> None:
        self.store = store
        self._record = record
        self.session_name = "aware::t-test"
        self.text = ""

    def restore_manifest(self) -> Manifest:
        return self.store.load()

    def ensure_window(self, record: SessionRecord) -> None:  # pragma: no cover - no-op
        pass

    def resize(self, record: SessionRecord, cols: int, rows: int) -> None:  # pragma: no cover - no-op
        pass

    def send_input(self, record: SessionRecord, data: str) -> None:  # pragma: no cover - no-op
        self.text += data

    def restart(self, record: SessionRecord) -> None:  # pragma: no cover - no-op
        self.text = ""

    def capture_pane_text(self, record: SessionRecord) -> str:
        return self.text


def test_daemon_stream_emits_output(tmp_path: Path) -> None:
    socket_path = Path(tempfile.gettempdir()) / f"aware-test-{uuid.uuid4().hex}.sock"
    manifest_path = tmp_path / "manifest.json"
    store = ManifestStore(manifest_path)

    record = SessionRecord(
        apt_id="apt-1",
        session_id="apt-1",
        tmux_window="apt-apt-1",
        shell="/bin/bash",
        cwd=tmp_path,
    )
    manifest = Manifest(thread="t-test", socket_path=socket_path, sessions=[record])
    store.write(manifest)

    manager = FakeSessionManager(store, record)
    manager.text = "hello\n"
    server = DaemonServer(
        thread="t-test",
        socket_path=socket_path,
        manifest_store=store,
        session_manager=manager,  # type: ignore[arg-type]
        poll_interval=0.05,
    )
    try:
        server.start()
    except PermissionError:
        pytest.skip("Unix sockets not permitted in test environment")

    client = TerminalDaemonClient(socket_path=socket_path, manifest_store=store)
    stream = client.attach_stream("apt-1", 80, 24)

    try:
        event = None
        start = time.time()
        while time.time() - start < 2.0:
            evt = stream.get_event(timeout=0.2)
            if evt and evt.get("type") == "output":
                event = evt
                break
        assert event is not None
        assert event["payload"]["data"].strip() == "hello"
    finally:
        stream.close()
        server.stop()
