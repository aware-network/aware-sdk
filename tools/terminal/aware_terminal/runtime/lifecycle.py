from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from ..daemon import (
    DaemonServer,
    SessionManager,
    ManifestStore,
    default_socket_path,
    manifest_path as default_manifest_path,
)
from .session import mark_session_status


@dataclass
class LifecycleResult:
    ok: bool
    message: str = ""
    error: Optional[str] = None
    socket_path: Optional[Path] = None
    server: Optional[DaemonServer] = None


@dataclass
class _DaemonHandle:
    server: DaemonServer
    socket_path: Path


_REGISTRY: Dict[str, _DaemonHandle] = {}
_LOCK = threading.Lock()
def _state_base() -> Path:
    base = os.environ.get("AWARE_STATE_HOME")
    return Path(base) if base else Path.home() / ".aware_state"


def _pid_root() -> Path:
    return _state_base() / "terminal_daemon"


def start_daemon(
    thread: str,
    *,
    socket_path: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    detach: bool = True,
    poll: bool = True,
    poll_timeout: float = 3.0,
    poll_interval: float = 0.5,
) -> LifecycleResult:
    """Start the daemon for a thread.

    When detach=True, the daemon is registered in the in-process registry so it can
    be stopped later via ``stop_daemon``. When detach=False, the caller is expected
    to manage the returned server instance.
    """

    socket_path = socket_path or default_socket_path(thread)
    manifest_file = manifest_path or default_manifest_path(thread)

    with _LOCK:
        handle = _REGISTRY.get(thread)
        if detach and handle:
            return LifecycleResult(
                ok=True,
                message="daemon_already_running",
                socket_path=handle.socket_path,
            )

    store = ManifestStore(manifest_file)
    manifest = store.load_or_create(thread, socket_path)

    try:
        manager = SessionManager(thread=thread, manifest_store=store, socket_path=socket_path)
    except RuntimeError as exc:
        return LifecycleResult(ok=False, error="tmux_error", message=str(exc), socket_path=socket_path)

    server = DaemonServer(
        thread=thread,
        socket_path=socket_path,
        manifest_store=store,
        session_manager=manager,
        poll_interval=poll_interval,
    )
    try:
        server.start()
    except PermissionError as exc:
        return LifecycleResult(ok=False, error="permission_error", message=str(exc), socket_path=socket_path)

    if poll and not _wait_for_socket(socket_path, poll_timeout):
        server.stop()
        return LifecycleResult(
            ok=False,
            error="socket_timeout",
            message="daemon socket was not created",
            socket_path=socket_path,
        )

    if detach:
        with _LOCK:
            _REGISTRY[thread] = _DaemonHandle(server=server, socket_path=socket_path)
        return LifecycleResult(ok=True, message="daemon_running", socket_path=socket_path)

    return LifecycleResult(ok=True, message="daemon_running", socket_path=socket_path, server=server)


def stop_daemon(thread: str) -> LifecycleResult:
    """Stop the daemon previously started via start_daemon(detach=True)."""

    with _LOCK:
        handle = _REGISTRY.pop(thread, None)

    socket_path = default_socket_path(thread)
    manifest_file = default_manifest_path(thread)
    store = ManifestStore(manifest_file)
    try:
        manifest = store.load()
    except FileNotFoundError:
        manifest = None

    if handle is None:
        # Best effort cleanup if socket still exists
        if socket_path.exists():
            try:
                socket_path.unlink()
            except OSError:
                pass
        return LifecycleResult(ok=False, error="not_running", message="daemon not registered", socket_path=socket_path)

    handle.server.stop()
    if handle.socket_path.exists():
        try:
            handle.socket_path.unlink()
        except OSError:
            pass
    if manifest:
        for record in manifest.sessions:
            mark_session_status(thread, record.session_id, "stopped", reason="daemon_stopped")
    return LifecycleResult(ok=True, message="daemon_stopped", socket_path=handle.socket_path)


def is_daemon_running(thread: str) -> bool:
    with _LOCK:
        if thread in _REGISTRY:
            return True
    socket_path = default_socket_path(thread)
    return socket_path.exists()


def launch_daemon_subprocess(
    thread: str,
    *,
    socket_path: Optional[Path] = None,
    poll_timeout: float = 3.0,
    poll_interval: float = 0.5,
) -> LifecycleResult:
    socket_path = socket_path or default_socket_path(thread)
    manifest_file = default_manifest_path(thread)
    store = ManifestStore(manifest_file)
    store.load_or_create(thread, socket_path)

    cmd = [
        sys.executable,
        "-m",
        "aware_terminal.cli",
        "daemon",
        "serve",
        "--thread",
        thread,
        "--socket",
        str(socket_path),
        "--poll-interval",
        str(poll_interval),
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    pid_root = _pid_root()
    pid_root.mkdir(parents=True, exist_ok=True)
    _pid_path(thread).write_text(str(proc.pid), encoding="utf-8")

    if _wait_for_socket(socket_path, poll_timeout):
        return LifecycleResult(ok=True, message="daemon_running", socket_path=socket_path)

    return LifecycleResult(
        ok=False,
        error="socket_timeout",
        message="daemon socket was not created",
        socket_path=socket_path,
    )


def terminate_daemon_subprocess(thread: str, *, timeout: float = 3.0) -> LifecycleResult:
    pid_path = _pid_path(thread)
    if not pid_path.exists():
        return LifecycleResult(ok=False, error="not_running", message="no pid file", socket_path=default_socket_path(thread))
    try:
        pid = int(pid_path.read_text(encoding="utf-8"))
    except ValueError:
        pid_path.unlink(missing_ok=True)
        return LifecycleResult(ok=False, error="invalid_pid", message="corrupted pid file")

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pid_path.unlink(missing_ok=True)
        return LifecycleResult(ok=False, error="not_running", message="process not found")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_process_alive(pid):
            pid_path.unlink(missing_ok=True)
            _cleanup_socket(thread)
            return LifecycleResult(ok=True, message="daemon_stopped", socket_path=default_socket_path(thread))
        time.sleep(0.1)

    return LifecycleResult(ok=False, error="timeout", message="failed to stop daemon")


def _pid_path(thread: str) -> Path:
    safe = thread.replace("/", "_")
    return _pid_root() / f"{safe}.pid"


def _wait_for_socket(path: Path, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.05)
    return False


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _cleanup_socket(thread: str) -> None:
    path = default_socket_path(thread)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
