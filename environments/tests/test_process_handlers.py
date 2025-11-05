from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from aware_environments.kernel.objects.process import handlers as process_handlers


def _setup_runtime(tmp_path: Path) -> Path:
    runtime_root = tmp_path / "docs" / "runtime" / "process"
    process_dir = runtime_root / "demo-process"
    thread_dir = process_dir / "threads" / "main"

    (thread_dir / "branches").mkdir(parents=True, exist_ok=True)
    (thread_dir / "pane_manifests").mkdir(parents=True, exist_ok=True)
    (thread_dir / "backlog").mkdir(parents=True, exist_ok=True)
    (process_dir / "backlog").mkdir(parents=True, exist_ok=True)

    process_payload = {
        "id": "process-uuid-1234",
        "title": "Demo Process",
        "description": "Runtime orchestration demo",
        "priority_level": "medium",
        "status": "active",
        "created_at": "2025-10-01T10:00:00Z",
        "updated_at": "2025-10-01T12:00:00Z",
    }
    (process_dir / "process.json").write_text(json.dumps(process_payload, indent=2) + "\n", encoding="utf-8")

    thread_payload = {
        "id": "thread-uuid-5678",
        "process_id": process_payload["id"],
        "thread_slug": "main",
        "title": "Main Thread",
        "description": "Primary coordination lane",
        "is_main": True,
        "thread_task_list": [],
        "created_at": "2025-10-01T10:10:00Z",
        "updated_at": "2025-10-01T11:10:00Z",
    }
    (thread_dir / "thread.json").write_text(json.dumps(thread_payload, indent=2) + "\n", encoding="utf-8")

    backlog_entry = process_dir / "backlog" / "2025-10-02-runtime.md"
    backlog_entry.write_text(
        "---\n"
        "title: Runtime Event\n"
        "created: 2025-10-02T09:00:00Z\n"
        "updated: 2025-10-02T09:05:00Z\n"
        "---\n\n"
        "Process level change recorded.\n",
        encoding="utf-8",
    )

    later_entry = process_dir / "backlog" / "2025-10-03-late.md"
    later_entry.write_text(
        "---\n"
        "title: Later Event\n"
        "created: 2025-10-03T09:00:00Z\n"
        "updated: 2025-10-03T09:05:00Z\n"
        "---\n\n"
        "Subsequent update.\n",
        encoding="utf-8",
    )

    return runtime_root


@pytest.fixture()
def runtime_root(tmp_path: Path) -> Path:
    return _setup_runtime(tmp_path)


def test_list_processes_returns_entries(runtime_root: Path) -> None:
    entries = process_handlers.list_processes(runtime_root)
    assert entries and entries[0]["slug"] == "demo-process"
    assert entries[0]["status"] == "active"
    assert entries[0]["thread_count"] == 1


def test_process_status_supports_identifier_and_slug(runtime_root: Path) -> None:
    payload = process_handlers.process_status(runtime_root, process="demo-process")
    assert payload["slug"] == "demo-process"
    identifier_payload = process_handlers.process_status(runtime_root, identifier=payload["uuid"])
    assert identifier_payload["slug"] == "demo-process"


def test_process_threads_returns_thread_entries(runtime_root: Path) -> None:
    threads = process_handlers.process_threads(runtime_root, process="demo-process")
    assert threads and threads[0]["thread_slug"] == "main"
    assert threads[0]["process_slug"] == "demo-process"
    assert threads[0]["is_main"] is True


def test_process_backlog_filters_with_since(runtime_root: Path) -> None:
    events = process_handlers.process_backlog(runtime_root, process="demo-process")
    assert len(events) == 2
    since = (datetime(2025, 10, 3, 8, 0, tzinfo=timezone.utc) - timedelta(days=0)).isoformat().replace("+00:00", "Z")
    filtered = process_handlers.process_backlog(runtime_root, process="demo-process", since=since)
    assert filtered and filtered[0]["event_type"] == "backlog"
    assert filtered[0]["summary"] == "Later Event"
