from __future__ import annotations

import queue
import socket
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .manifest import ManifestStore
from .models import Manifest, ProtocolMessage, SessionRecord
from .ipc import write_message, read_message


class DaemonStream:
    """Streaming helper returning output events from an attached session."""

    def __init__(self, sock: socket.socket, rfile, wfile, session_id: str):
        self.sock = sock
        self.rfile = rfile
        self.wfile = wfile
        self.session_id = session_id
        self.stop_event = threading.Event()
        self.queue: queue.Queue[Optional[ProtocolMessage]] = queue.Queue()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._closed = False
        self.terminated = False

    def _read_loop(self) -> None:
        try:
            while not self.stop_event.is_set():
                try:
                    message = read_message(self.rfile)
                except EOFError:
                    break
                self.queue.put(message)
                if message.get("type") == "status" and message.get("payload", {}).get("status") == "detached":
                    break
        except Exception:
            pass
        finally:
            self.queue.put(None)
            self.terminated = True

    def get_event(self, timeout: Optional[float] = None) -> Optional[ProtocolMessage]:
        try:
            item = self.queue.get(timeout=timeout)
        except queue.Empty:
            return None
        if item is None:
            self.terminated = True
        return item

    def events(self, timeout: Optional[float] = None) -> Iterator[ProtocolMessage]:
        while True:
            item = self.get_event(timeout)
            if item is None:
                break
            yield item

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            detach_id = f"detach-{uuid.uuid4()}"
            write_message(
                self.wfile,
                {"id": detach_id, "type": "detach", "payload": {"session": self.session_id}},
            )
        except Exception:
            pass
        self.stop_event.set()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
        self._reader.join(timeout=1.0)
        self.terminated = True


class TerminalDaemonClient:
    """Client shim for the aware-terminal daemon.

    If the Unix socket is unavailable, `list_sessions` falls back to reading the
    manifest directly (read-only mode). Mutation commands require the daemon.
    """

    def __init__(
        self,
        socket_path: Path,
        manifest_store: Optional[ManifestStore] = None,
        timeout: float = 5.0,
    ) -> None:
        self.socket_path = socket_path
        self.manifest_store = manifest_store
        self.timeout = timeout

    # Public API ------------------------------------------------------------------
    def list_sessions(self) -> List[SessionRecord]:
        if self.socket_path.exists():
            payload = self._command("list_sessions", {})
            sessions_payload = payload.get("sessions", [])
            return [SessionRecord.model_validate(item) for item in sessions_payload]
        if self.manifest_store:
            manifest = self.manifest_store.load()
            return manifest.sessions
        raise FileNotFoundError(f"Daemon socket not found: {self.socket_path}")

    def attach(self, session_id: str, cols: int, rows: int) -> None:
        self._require_daemon()
        self._command("attach", {"session": session_id, "cols": cols, "rows": rows})

    def detach(self, session_id: str) -> None:
        self._require_daemon()
        self._command("detach", {"session": session_id})

    def send_input(self, session_id: str, data: str) -> None:
        self._require_daemon()
        self._command("input", {"session": session_id, "data": data})

    def resize(self, session_id: str, cols: int, rows: int) -> None:
        self._require_daemon()
        self._command("resize", {"session": session_id, "cols": cols, "rows": rows})

    def restart(self, session_id: str) -> None:
        self._require_daemon()
        self._command("restart", {"session": session_id})

    # Internal helpers -------------------------------------------------------------
    def _require_daemon(self) -> None:
        if not self.socket_path.exists():
            raise FileNotFoundError(f"Daemon socket not found: {self.socket_path}")

    def _command(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        message: ProtocolMessage = {
            "id": command,
            "type": command,
            "payload": payload,
        }
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect(str(self.socket_path))
            with sock.makefile("wb") as wfile:
                write_message(wfile, message)
            with sock.makefile("rb") as rfile:
                response = read_message(rfile)
        if not response.get("ok", True):
            error = response.get("error", "unknown daemon error")
            raise RuntimeError(error)
        return response.get("payload", {})

    # Streaming -----------------------------------------------------------------
    def attach_stream(self, session_id: str, cols: int, rows: int) -> DaemonStream:
        """Attach to a session and return a stream of output/status events."""

        self._require_daemon()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(str(self.socket_path))
        rfile = sock.makefile("rb")
        wfile = sock.makefile("wb")

        message: ProtocolMessage = {
            "id": f"attach-{uuid.uuid4()}",
            "type": "attach",
            "payload": {"session": session_id, "cols": cols, "rows": rows},
        }
        write_message(wfile, message)
        response = read_message(rfile)
        if not response.get("ok", True):
            sock.close()
            raise RuntimeError(response.get("error", "daemon error"))

        return DaemonStream(sock=sock, rfile=rfile, wfile=wfile, session_id=session_id)


class ManifestOnlyClient(TerminalDaemonClient):
    """Fallback client that never attempts socket connections."""

    def __init__(self, manifest: Manifest) -> None:
        self.manifest = manifest

    def list_sessions(self) -> List[SessionRecord]:
        return self.manifest.sessions

    def _require_daemon(self) -> None:  # pragma: no cover - override
        raise FileNotFoundError("Daemon not available in manifest-only mode")

    def _command(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
        raise FileNotFoundError("Daemon not available in manifest-only mode")
