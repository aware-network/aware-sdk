from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Dict, Optional

from .ipc import read_message, write_message
from .manifest import ManifestStore
from .models import Manifest, ProtocolMessage, SessionRecord
from .session_manager import SessionManager


class StreamWorker:
    """Background poller that emits incremental tmux pane output for a session."""

    def __init__(
        self,
        session_manager: SessionManager,
        record: SessionRecord,
        send_event,
        poll_interval: float = 0.5,
    ) -> None:
        self.session_manager = session_manager
        self.record = record
        self.send_event = send_event
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._last_size = 0

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=1.0)

    def _run(self) -> None:
        self.send_event(
            "status",
            {"session": self.record.session_id, "status": "attached"},
        )
        while not self._stop_event.is_set():
            try:
                text = self.session_manager.capture_pane_text(self.record)
            except Exception:
                time.sleep(self.poll_interval)
                continue

            if text is None:
                text = ""

            current_size = len(text)
            if current_size < self._last_size:
                # Pane cleared; send full buffer
                if text:
                    self.send_event("output", {"session": self.record.session_id, "data": text})
                self._last_size = current_size
            elif current_size > self._last_size:
                chunk = text[self._last_size :]
                if chunk:
                    self.send_event("output", {"session": self.record.session_id, "data": chunk})
                self._last_size = current_size

            time.sleep(self.poll_interval)

        self.send_event(
            "status",
            {"session": self.record.session_id, "status": "detached"},
        )


@dataclass
class ClientState:
    sock: socket.socket
    rfile: BinaryIO
    wfile: BinaryIO
    lock: threading.Lock = field(default_factory=threading.Lock)
    streams: Dict[str, StreamWorker] = field(default_factory=dict)


class DaemonServer:
    """Unix-socket daemon that exposes tmux session operations with streaming output."""

    def __init__(
        self,
        thread: str,
        socket_path: Path,
        manifest_store: ManifestStore,
        session_manager: SessionManager,
        poll_interval: float = 0.5,
    ) -> None:
        self.thread = thread
        self.socket_path = socket_path
        self.manifest_store = manifest_store
        self.session_manager = session_manager
        self.poll_interval = poll_interval

        self._stop_event = threading.Event()
        self._server_socket: Optional[socket.socket] = None
        self._accept_thread: Optional[threading.Thread] = None

        # Ensure tmux + panes exist
        self.session_manager.restore_manifest()

    # Lifecycle ------------------------------------------------------------------
    def start(self) -> None:
        if self.socket_path.exists():
            self.socket_path.unlink()
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)

        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(self.socket_path))
        server_sock.listen()
        server_sock.settimeout(0.5)
        self._server_socket = server_sock

        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._server_socket is not None:
            try:
                self._server_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._server_socket.close()
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=1.0)
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass

    def _accept_loop(self) -> None:
        assert self._server_socket is not None
        while not self._stop_event.is_set():
            try:
                client_sock, _ = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()

    # Client handling ------------------------------------------------------------
    def _handle_client(self, sock: socket.socket) -> None:
        with sock:
            rfile = sock.makefile("rb")
            wfile = sock.makefile("wb")
            state = ClientState(sock=sock, rfile=rfile, wfile=wfile)

            try:
                while not self._stop_event.is_set():
                    try:
                        message = read_message(state.rfile)
                    except EOFError:
                        break
                    response = self._dispatch(message, state)
                    if response is not None:
                        self._send_response(state, response)
            finally:
                self._stop_streams(state)

    def _send_response(self, state: ClientState, message: ProtocolMessage) -> None:
        with state.lock:
            try:
                write_message(state.wfile, message)
            except OSError:
                pass

    def _send_event(self, state: ClientState, event_type: str, payload: dict) -> None:
        with state.lock:
            try:
                write_message(state.wfile, {"type": event_type, "payload": payload})
            except OSError:
                pass

    def _stop_streams(self, state: ClientState) -> None:
        for worker in list(state.streams.values()):
            worker.stop()
        state.streams.clear()

    # Command dispatch -----------------------------------------------------------
    def _dispatch(self, message: ProtocolMessage, state: ClientState) -> ProtocolMessage:
        command = message.get("type") or message.get("command")
        payload = message.get("payload") or {}
        response: ProtocolMessage = {"id": message.get("id", ""), "type": command or "", "ok": True, "payload": {}}

        try:
            if command == "list_sessions":
                manifest = self._reload_manifest()
                response["payload"] = {"sessions": [record.as_dict() for record in manifest.sessions]}
            elif command == "attach":
                session_id = payload.get("session")
                cols = int(payload.get("cols", 80))
                rows = int(payload.get("rows", 24))
                record = self._lookup_session(session_id)
                self.session_manager.ensure_window(record)
                self.session_manager.resize(record, cols, rows)
                # Start streaming worker
                self._stop_stream(state, record.session_id)
                worker = StreamWorker(
                    session_manager=self.session_manager,
                    record=record,
                    send_event=lambda et, pl: self._send_event(state, et, pl),
                    poll_interval=self.poll_interval,
                )
                state.streams[record.session_id] = worker
                worker.start()
                self._touch_session(record.session_id)
            elif command == "detach":
                session_id = payload.get("session")
                self._stop_stream(state, session_id)
                self._touch_session(session_id)
            elif command == "input":
                session_id = payload.get("session")
                data = payload.get("data", "")
                record = self._lookup_session(session_id)
                self.session_manager.send_input(record, data)
                self._touch_session(record.session_id)
            elif command == "resize":
                session_id = payload.get("session")
                cols = int(payload.get("cols", 80))
                rows = int(payload.get("rows", 24))
                record = self._lookup_session(session_id)
                self.session_manager.resize(record, cols, rows)
                self._touch_session(record.session_id)
            elif command == "restart":
                session_id = payload.get("session")
                record = self._lookup_session(session_id)
                self.session_manager.restart(record)
                self._touch_session(record.session_id)
            else:
                response["ok"] = False
                response["error"] = f"Unknown command: {command}"
        except Exception as exc:
            response["ok"] = False
            response["error"] = str(exc)

        return response

    def _stop_stream(self, state: ClientState, session_id: str | None) -> None:
        if not session_id:
            return
        worker = state.streams.pop(session_id, None)
        if worker:
            worker.stop()

    def _reload_manifest(self) -> Manifest:
        return self.manifest_store.load()

    def _lookup_session(self, session_id: str) -> SessionRecord:
        manifest = self._reload_manifest()
        for record in manifest.sessions:
            if record.session_id == session_id:
                return record
        raise ValueError(f"Session not found: {session_id}")

    def _touch_session(self, session_id: str) -> None:
        manifest = self._reload_manifest()
        now = datetime.now(timezone.utc)
        updated: list[SessionRecord] = []
        for record in manifest.sessions:
            if record.session_id == session_id:
                updated.append(record.model_copy(update={"last_active_at": now}))
            else:
                updated.append(record)
        updated_manifest = manifest.copy(update={"sessions": updated, "updated_at": now})
        self.manifest_store.write(updated_manifest)
