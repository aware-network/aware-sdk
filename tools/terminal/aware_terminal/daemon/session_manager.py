from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..core.util import run, which
from .manifest import ManifestStore
from .models import Manifest, SessionRecord, _utc_now


def tmux_session_name(thread: str) -> str:
    sanitized = thread.replace(":", "-")
    return f"aware__{sanitized}"


@dataclass
class SessionManager:
    thread: str
    manifest_store: ManifestStore
    socket_path: Path
    tmux_path: Optional[str] = None

    def __post_init__(self) -> None:
        self.tmux_path = self.tmux_path or which("tmux")
        if not self.tmux_path:
            raise RuntimeError("tmux binary not found. Install tmux and ensure it is on PATH.")
        self.session_name = tmux_session_name(self.thread)

    # Manifest helpers -----------------------------------------------------------------
    def load_manifest(self) -> Manifest:
        return self.manifest_store.load_or_create(self.thread, self.socket_path)

    def save_manifest(self, manifest: Manifest) -> None:
        self.manifest_store.write(manifest)

    # tmux helpers ---------------------------------------------------------------------
    def _tmux(self, args: List[str], check: bool = True) -> int:
        result = run([self.tmux_path] + args, check=check)
        return result.code

    def ensure_server(self) -> None:
        self._tmux(["start-server"], check=False)

    def ensure_session(self, manifest: Manifest) -> None:
        exists = self._tmux(["has-session", "-t", self.session_name], check=False) == 0
        if exists:
            return
        if manifest.sessions:
            first = manifest.sessions[0]
            cmd = [
                "new-session",
                "-d",
                "-s",
                self.session_name,
                "-n",
                first.tmux_window,
                "-c",
                str(first.cwd),
            ]
            if first.start_script:
                cmd += ["bash", "-lc", first.start_script]
            else:
                cmd += [first.shell]
            result = run([self.tmux_path] + cmd, check=False)
            if result.code != 0 and "duplicate session" not in result.err:
                raise RuntimeError(f"tmux new-session failed: {result.err.strip()}")
        else:
            result = run([self.tmux_path, "new-session", "-d", "-s", self.session_name], check=False)
            if result.code != 0 and "duplicate session" not in result.err:
                raise RuntimeError(f"tmux new-session failed: {result.err.strip()}")
        if self._tmux(["has-session", "-t", self.session_name], check=False) != 0:
            raise RuntimeError(f"Failed to create tmux session {self.session_name}")

    def list_windows(self) -> List[str]:
        out_code = run([self.tmux_path, "list-windows", "-t", self.session_name, "-F", "#{window_name}"], check=False)
        if out_code.code != 0:
            return []
        names = []
        for line in out_code.out.splitlines():
            line = line.strip()
            if line:
                names.append(line)
        return names

    def ensure_window(self, record: SessionRecord) -> None:
        target = f"{self.session_name}:{record.tmux_window}"
        exists = record.tmux_window in self.list_windows()
        if exists:
            return
        cmd = [
            "new-window",
            "-d",
            "-t",
            self.session_name,
            "-n",
            record.tmux_window,
            "-c",
            str(record.cwd),
        ]
        if record.start_script:
            cmd += ["bash", "-lc", record.start_script]
        else:
            cmd += [record.shell]
        result = run([self.tmux_path] + cmd, check=False)
        if result.code != 0 and "duplicate" not in result.err:
            raise RuntimeError(f"tmux new-window failed: {result.err.strip()}")

    def restore_manifest(self) -> Manifest:
        manifest = self.load_manifest()
        self.ensure_server()
        self.ensure_session(manifest)
        for record in manifest.sessions:
            self.ensure_window(record)
        return manifest

    # Session operations ---------------------------------------------------------------
    def register_session(
        self,
        session_id: str,
        shell: str,
        cwd: Path,
        *,
        terminal_id: Optional[str] = None,
        apt_id: Optional[str] = None,
        tmux_window: Optional[str] = None,
        start_script: Optional[str] = None,
        provider: Optional[str] = None,
        command: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> SessionRecord:
        manifest = self.load_manifest()
        self.ensure_server()
        if not terminal_id and not apt_id:
            raise ValueError("register_session requires terminal_id or apt_id")
        window_name = tmux_window
        if window_name is None:
            if terminal_id:
                window_name = f"term-{terminal_id}"
            elif apt_id:
                window_name = f"apt-{apt_id}"
        record = SessionRecord(
            session_id=session_id,
            tmux_window=window_name,
            shell=shell,
            cwd=cwd,
            start_script=start_script,
            terminal_id=terminal_id,
            apt_id=apt_id,
            provider=provider,
            command=command,
            env=env,
            created_at=_utc_now(),
            last_active_at=_utc_now(),
        )
        manifest = self.manifest_store.update_session(manifest, record)
        persisted = next(sess for sess in manifest.sessions if sess.session_id == record.session_id)
        self.ensure_session(manifest)
        self.ensure_window(persisted)
        return persisted

    def remove_session(self, session_id: str) -> Manifest:
        manifest = self.load_manifest()
        updated = self.manifest_store.remove_session(manifest, session_id)
        return updated

    def session_target(self, session_id: str) -> str:
        window = session_id if session_id.startswith("apt-") else f"apt-{session_id}"
        return f"{self.session_name}:{window}"

    def send_input(self, record: SessionRecord, data: str) -> None:
        target = f"{self.session_name}:{record.tmux_window}"
        self._tmux(["send-keys", "-t", target, "-l", data], check=False)

    def send_enter(self, record: SessionRecord) -> None:
        target = f"{self.session_name}:{record.tmux_window}"
        self._tmux(["send-keys", "-t", target, "C-m"], check=False)

    def resize(self, record: SessionRecord, cols: int, rows: int) -> None:
        target = f"{self.session_name}:{record.tmux_window}"
        self._tmux(["resize-pane", "-t", target, "-x", str(cols), "-y", str(rows)], check=False)

    def restart(self, record: SessionRecord) -> None:
        target = f"{self.session_name}:{record.tmux_window}"
        cmd: List[str] = ["respawn-pane", "-t", target, "-k"]
        if record.start_script:
            cmd += ["bash", "-lc", record.start_script]
        else:
            cmd.append(record.shell)
        self._tmux(cmd, check=False)

    def capture_pane_text(self, record: SessionRecord) -> str:
        target = f"{self.session_name}:{record.tmux_window}"
        result = run([self.tmux_path, "capture-pane", "-p", "-t", target], check=False)
        return result.out
