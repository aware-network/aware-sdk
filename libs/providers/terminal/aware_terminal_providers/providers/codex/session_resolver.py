"""Codex session resolver utilities."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_PATTERNS = ("codex", "node")


@dataclass
class SessionInfo:
    session_id: str
    log_path: Path
    pid: Optional[int] = None


def _iter_codex_pids(patterns: Iterable[str]) -> Iterable[int]:
    try:
        output = subprocess.check_output(["ps", "-Ao", "pid,comm"], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    for line in output.splitlines()[1:]:
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        pid_str, command = parts
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        if any(command.endswith(pat) for pat in patterns):
            yield pid


def _lsof_session_log(pid: int) -> Optional[Path]:
    try:
        result = subprocess.run(
            ["lsof", "-Fn", "-p", str(pid)],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.startswith("n"):
            continue
        path_str = line[1:]
        if "/sessions/" in path_str and path_str.endswith(".jsonl"):
            return Path(path_str)
    return None


_uuid_regex = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _normalize_session_id(value: str, log_path: Path) -> str:
    match = _uuid_regex.search(value)
    if match:
        return match.group(0)
    match = _uuid_regex.search(log_path.stem)
    if match:
        return match.group(0)
    return value


def _extract_session_id(log_path: Path) -> Optional[str]:
    try:
        with log_path.open("r", encoding="utf-8", errors="ignore") as fh:
            for _ in range(10):
                line = fh.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                value = payload.get("session_id")
                if isinstance(value, str) and value:
                    return _normalize_session_id(value, log_path)
    except OSError:
        pass
    return _normalize_session_id(log_path.stem, log_path)


def discover_active_session(patterns: Iterable[str] = DEFAULT_PATTERNS) -> Optional[SessionInfo]:
    for pid in _iter_codex_pids(patterns):
        log_path = _lsof_session_log(pid)
        if not log_path:
            continue
        session_id = _extract_session_id(log_path)
        if session_id:
            return SessionInfo(session_id=session_id, log_path=log_path, pid=pid)
    return None


def discover_latest_session(sessions_dir: Path) -> Optional[SessionInfo]:
    if not sessions_dir.exists():
        return None
    try:
        entries = list(sessions_dir.rglob("*.jsonl"))
    except OSError:
        return None
    if not entries:
        return None
    entries.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for path in entries:
        session_id = _extract_session_id(path)
        if session_id:
            return SessionInfo(session_id=session_id, log_path=path, pid=None)
    return None


def resolve_codex_session(
    *,
    sessions_dir: Optional[Path] = None,
    patterns: Iterable[str] = DEFAULT_PATTERNS,
) -> Optional[SessionInfo]:
    candidate = discover_active_session(patterns)
    if candidate:
        return candidate
    base_dir = sessions_dir
    if base_dir is None:
        codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        base_dir = codex_home / "sessions"
    return discover_latest_session(base_dir)


__all__ = [
    "SessionInfo",
    "resolve_codex_session",
]
