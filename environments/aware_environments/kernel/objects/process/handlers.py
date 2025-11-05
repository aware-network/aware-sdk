"""Kernel handlers for orchestrator process object."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .._shared.fs_utils import ensure_iso_timestamp
from .._shared.runtime_models import RuntimeEvent
from ..thread.schemas import ThreadEntry
from ..thread.fs import ThreadFSAdapter
from .fs import ProcessFSAdapter
from .schemas import ProcessEntry


def _coerce_process_identifier(identifier: Optional[str], process: Optional[str]) -> str:
    if identifier and str(identifier).strip():
        return str(identifier)
    if process and str(process).strip():
        return str(process)
    raise ValueError("Process identifier is required.")


def _process_entry_to_dict(entry: ProcessEntry) -> Dict[str, object]:
    payload = entry.model_dump_json_ready()
    payload.update(
        {
            "id": entry.process_id or entry.slug,
            "uuid": entry.process_id,
            "slug": entry.slug,
            "path": str(entry.directory),
            "priority_level": entry.priority_level,
            "status": entry.status,
            "thread_count": entry.thread_count,
            "latest_backlog_at": ensure_iso_timestamp(entry.latest_backlog_at),
            "created_at": ensure_iso_timestamp(entry.created_at),
            "updated_at": ensure_iso_timestamp(entry.updated_at),
        }
    )
    payload.pop("directory", None)
    return payload


def _thread_entry_to_dict(entry: ThreadEntry) -> Dict[str, object]:
    payload = entry.model_dump_json_ready()
    payload.update(
        {
            "id": entry.thread_id or f"{entry.process_slug}/{entry.thread_slug}",
            "uuid": entry.thread_id,
            "process_slug": entry.process_slug,
            "thread_slug": entry.thread_slug,
            "path": str(entry.directory),
            "pane_kinds": list(entry.pane_kinds),
            "conversation_count": entry.conversation_count,
            "branch_count": entry.branch_count,
            "is_main": entry.is_main,
            "created_at": ensure_iso_timestamp(entry.created_at),
            "updated_at": ensure_iso_timestamp(entry.updated_at),
        }
    )
    payload.pop("directory", None)
    payload["pane_kinds"] = list(entry.pane_kinds)
    return payload


def _sanitize_metadata(value):
    if isinstance(value, datetime):
        return ensure_iso_timestamp(value)
    if isinstance(value, dict):
        return {key: _sanitize_metadata(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value]
    return value


def _runtime_event_to_dict(event: RuntimeEvent) -> Dict[str, object]:
    payload = event.model_dump_json_ready()
    payload.update(
        {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": ensure_iso_timestamp(event.timestamp),
            "path": str(event.path),
            "summary": event.summary,
            "metadata": _sanitize_metadata(event.metadata),
        }
    )
    return payload


def list_processes(runtime_root: Path, *, status: Optional[str] = None) -> List[Dict[str, object]]:
    adapter = ProcessFSAdapter(runtime_root)
    entries = adapter.list_processes(status=status)
    return [_process_entry_to_dict(entry) for entry in entries]


def process_status(
    runtime_root: Path,
    identifier: Optional[str] = None,
    *,
    process: Optional[str] = None,
) -> Dict[str, object]:
    adapter = ProcessFSAdapter(runtime_root)
    target = _coerce_process_identifier(identifier, process)
    entry = adapter.get_process(target)
    if entry is None:
        raise ValueError(f"Process '{target}' not found.")
    return _process_entry_to_dict(entry)


def process_threads(
    runtime_root: Path,
    identifier: Optional[str] = None,
    *,
    process: Optional[str] = None,
) -> List[Dict[str, object]]:
    adapter = ProcessFSAdapter(runtime_root)
    target = _coerce_process_identifier(identifier, process)
    entry = adapter.get_process(target)
    if entry is None:
        raise ValueError(f"Process '{target}' not found.")
    thread_adapter = ThreadFSAdapter(runtime_root)
    threads = thread_adapter.list_threads(process_slug=entry.slug)
    return [_thread_entry_to_dict(thread) for thread in threads]


def process_backlog(
    runtime_root: Path,
    identifier: Optional[str] = None,
    *,
    process: Optional[str] = None,
    since: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, object]]:
    adapter = ProcessFSAdapter(runtime_root)
    target = _coerce_process_identifier(identifier, process)
    entry = adapter.get_process(target)
    if entry is None:
        raise ValueError(f"Process '{target}' not found.")
    from .._shared.timeline import ensure_datetime  # local import to avoid circular

    since_dt = ensure_datetime(since) if since else None
    events = adapter.collect_backlog(entry, since=since_dt, limit=limit)
    return [_runtime_event_to_dict(evt) for evt in events]


__all__ = [
    "list_processes",
    "process_status",
    "process_threads",
    "process_backlog",
]
