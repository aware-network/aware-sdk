from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ..daemon import SessionManager, ManifestStore, default_socket_path, manifest_path
from ..daemon.paths import aware_root
from ..providers import ProviderActionResult, get_provider
from ..providers.base import ProviderSessionResult, ProviderContext


@dataclass
class EnsureProviderSessionResult:
    session_id: str
    tmux_window: str
    socket_path: Path
    command: str = ""
    provider: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)


_SESSION_STATUS_RUNNING = "running"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sessions_dir() -> Path:
    root = aware_root() / "sessions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _session_receipt_path(session_id: str) -> Path:
    return _sessions_dir() / f"{session_id}.json"


def _session_receipt_path_soft(session_id: str) -> Path:
    return aware_root() / "sessions" / f"{session_id}.json"


def _current_session_path() -> Path:
    return aware_root() / "sessions" / "current_session.json"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _descriptor_path(thread: str, terminal_id: Optional[str]) -> Optional[str]:
    if not terminal_id:
        return None
    return str(aware_root() / "threads" / thread / "terminals" / f"{terminal_id}.json")


def _normalize_mapping(values: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not values:
        return {}
    normalized: Dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            normalized[str(key)] = value
        else:
            normalized[str(key)] = str(value)
    return normalized


def _set_current_session(payload: Dict[str, Any]) -> None:
    pointer = {
        "session_id": payload.get("session_id"),
        "thread_id": payload.get("thread_id"),
        "terminal_id": payload.get("terminal_id"),
        "apt_id": payload.get("apt_id"),
        "provider": payload.get("provider"),
        "status": payload.get("status", _SESSION_STATUS_RUNNING),
        "updated_at": payload.get("updated_at", _now_iso()),
    }
    _write_json(_current_session_path(), pointer)


def _clear_current_session(session_id: str) -> None:
    path = _current_session_path()
    data = _read_json(path)
    if not data:
        return
    if data.get("session_id") == session_id:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _write_session_receipt(
    *,
    thread: str,
    session_id: str,
    terminal_id: Optional[str],
    apt_id: Optional[str],
    provider: Optional[str],
    metadata: Dict[str, Any],
    env: Dict[str, str],
) -> None:
    receipt_path = _session_receipt_path(session_id)
    existing = _read_json(receipt_path) or {}
    created_at = existing.get("created_at", _now_iso())
    receipt = {
        "session_id": session_id,
        "thread_id": thread,
        "terminal_id": terminal_id,
        "apt_id": apt_id,
        "provider": provider,
        "descriptor_path": _descriptor_path(thread, terminal_id),
        "metadata": _normalize_mapping(metadata),
        "env": _normalize_mapping(env),
        "status": _SESSION_STATUS_RUNNING,
        "created_at": created_at,
        "updated_at": _now_iso(),
    }
    _write_json(receipt_path, receipt)
    _set_current_session(receipt)


def mark_session_status(thread: str, session_id: str, status: str, *, reason: Optional[str] = None) -> None:
    if not session_id:
        return
    receipt_path = _session_receipt_path_soft(session_id)
    data = _read_json(receipt_path)
    if not data:
        return
    data["status"] = status
    data["thread_id"] = thread
    data["updated_at"] = _now_iso()
    if reason:
        data["reason"] = reason
    _write_json(receipt_path, data)
    if status == _SESSION_STATUS_RUNNING:
        _set_current_session(data)
    else:
        _clear_current_session(session_id)


def get_current_session() -> Optional[Dict[str, Any]]:
    return _read_json(_current_session_path())


def discover_provider_session(
    thread: str,
    provider_slug: str,
    *,
    terminal_id: Optional[str] = None,
    apt_id: Optional[str] = None,
) -> ProviderActionResult:
    provider = get_provider(provider_slug)
    if provider is None:
        raise ValueError(f"Provider '{provider_slug}' not registered")

    context = ProviderContext(
        thread_id=thread,
        terminal_id=terminal_id,
        apt_id=apt_id,
        descriptor=None,
    )

    result = provider.resolve_active_session(context=context)
    if not isinstance(result, ProviderActionResult):
        raise TypeError("resolve_active_session must return ProviderActionResult")

    data = dict(result.data or {})
    data.setdefault("provider", provider_slug)

    session_id = str(data.get("session_id") or "")
    if not result.success or not session_id:
        result.data = data
        return result

    env_payload = data.get("env")
    env_map = (
        {str(k): str(v) for k, v in env_payload.items() if v is not None}
        if isinstance(env_payload, dict)
        else {}
    )
    env_map.setdefault("AWARE_PROVIDER_SESSION_ID", session_id)

    resolution_payload = data.get("resolution")
    resolution_meta = dict(resolution_payload) if isinstance(resolution_payload, dict) else {}
    resolution_meta.setdefault("provider", provider_slug)
    resolution_meta.setdefault("thread_id", thread)
    if terminal_id:
        resolution_meta.setdefault("terminal_id", terminal_id)
    if apt_id:
        resolution_meta.setdefault("apt_id", apt_id)

    _write_session_receipt(
        thread=thread,
        session_id=session_id,
        terminal_id=terminal_id,
        apt_id=apt_id,
        provider=provider_slug,
        metadata=resolution_meta,
        env=env_map,
    )

    data["env"] = env_map
    data["resolution"] = resolution_meta
    data["receipt_path"] = str(_session_receipt_path(session_id))
    result.data = data
    return result


def ensure_provider_session(
    thread: str,
    provider_slug: str,
    *,
    apt_id: Optional[str] = None,
    terminal_id: Optional[str] = None,
    resume: bool = False,
    existing_session_id: Optional[str] = None,
) -> EnsureProviderSessionResult:
    if not apt_id and not terminal_id:
        raise ValueError("ensure_provider_session requires apt_id or terminal_id")
    provider = get_provider(provider_slug)
    if provider is None:
        raise ValueError(f"Provider '{provider_slug}' not registered")

    manifest_file = manifest_path(thread)
    socket = default_socket_path(thread)
    store = ManifestStore(manifest_file)
    manager = SessionManager(thread=thread, manifest_store=store, socket_path=socket)

    context = ProviderContext(
        thread_id=thread,
        terminal_id=terminal_id,
        apt_id=apt_id,
        descriptor=None,
    )

    if resume:
        result = provider.resume(session_id=existing_session_id, context=context)
    else:
        result = provider.launch(resume=False, context=context)
    env_map = dict(result.environment)
    if apt_id and "APT_ID" not in env_map:
        env_map["APT_ID"] = apt_id
        env_map.setdefault("AWARE_APT_ID", apt_id)
    if terminal_id and "AWARE_TERMINAL_ID" not in env_map:
        env_map["AWARE_TERMINAL_ID"] = terminal_id
    if thread and "AWARE_THREAD_ID" not in env_map:
        env_map["AWARE_THREAD_ID"] = thread
    metadata = dict(result.extra_metadata)
    metadata.setdefault("provider", provider_slug)
    if apt_id:
        metadata.setdefault("apt_id", apt_id)
    if terminal_id:
        metadata.setdefault("terminal_id", terminal_id)
    if thread:
        metadata.setdefault("thread_id", thread)
    command_str = _format_command(result.command, env_map)
    cwd_raw = result.cwd if result.cwd is not None else Path.cwd()
    cwd = cwd_raw if isinstance(cwd_raw, Path) else Path(str(cwd_raw))

    session_record = manager.register_session(
        session_id=result.session_id,
        shell="/bin/bash",
        cwd=cwd,
        terminal_id=terminal_id,
        apt_id=apt_id,
        tmux_window=None,
        start_script=command_str or None,
        provider=provider_slug,
        command=result.command,
        env=env_map,
    )

    # Run command in tmux pane if launching fresh
    if command_str:
        manager.send_input(session_record, command_str)
        manager.send_enter(session_record)

    _write_session_receipt(
        thread=thread,
        session_id=session_record.session_id,
        terminal_id=session_record.terminal_id,
        apt_id=session_record.apt_id,
        provider=provider_slug,
        metadata=metadata,
        env=env_map,
    )

    return EnsureProviderSessionResult(
        session_id=session_record.session_id,
        tmux_window=session_record.tmux_window,
        command=command_str,
        socket_path=socket,
        provider=provider_slug,
        metadata=metadata,
        env=env_map,
    )


def _format_command(command: Optional[list[str]], env: Dict[str, str]) -> str:
    if not command:
        return ""
    env_prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in env.items()) if env else ""
    cmd = " ".join(shlex.quote(part) for part in command)
    return f"{env_prefix} {cmd}".strip()


def ensure_terminal_session(
    thread: str,
    terminal_id: str,
    *,
    cwd: Optional[Path] = None,
    shell: str = "/bin/bash",
) -> EnsureProviderSessionResult:
    manifest_file = manifest_path(thread)
    socket = default_socket_path(thread)
    store = ManifestStore(manifest_file)
    manager = SessionManager(thread=thread, manifest_store=store, socket_path=socket)

    working_dir = cwd or Path.cwd()
    session_record = manager.register_session(
        session_id=terminal_id,
        shell=shell,
        cwd=working_dir,
        terminal_id=terminal_id,
        apt_id=None,
        tmux_window=None,
        start_script=None,
        provider=None,
        command=None,
        env=None,
    )

    _write_session_receipt(
        thread=thread,
        session_id=session_record.session_id,
        terminal_id=session_record.terminal_id,
        apt_id=session_record.apt_id,
        provider=None,
        metadata={},
        env={},
    )

    return EnsureProviderSessionResult(
        session_id=session_record.session_id,
        tmux_window=session_record.tmux_window,
        command="",
        socket_path=socket,
        provider=None,
        metadata={},
        env={},
    )
