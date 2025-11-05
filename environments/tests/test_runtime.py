from pathlib import Path
import json
from uuid import UUID

from aware_environments.kernel.objects.process.fs import ProcessFSAdapter
from aware_environments.kernel.objects.thread.fs import ThreadFSAdapter
from aware_environments.kernel.objects._shared.runtime_models import RuntimeEvent
from aware_environments.kernel.objects.process.schemas import ProcessEntry
from aware_environments.kernel.objects.thread.schemas import (
    ThreadEntry,
    ThreadParticipant,
    ThreadParticipantsManifest,
    ThreadParticipantType,
    ThreadParticipantRole,
    ThreadParticipantStatus,
    ThreadParticipantIdentityAgent,
)


def _make_runtime(tmp_path: Path) -> Path:
    runtime_root = tmp_path / "docs" / "runtime" / "process"
    thread_dir = runtime_root / "demo" / "threads" / "main"
    (thread_dir / "branches").mkdir(parents=True, exist_ok=True)
    (thread_dir / "pane_manifests").mkdir(parents=True, exist_ok=True)
    (thread_dir / "conversations").mkdir(parents=True, exist_ok=True)
    (thread_dir / "backlog").mkdir(parents=True, exist_ok=True)

    (runtime_root / "demo" / "process.json").write_text(
        json.dumps(
            {
                "id": "proc-uuid",
                "title": "Demo",
                "description": "Demo process",
                "priority_level": "high",
                "status": "active",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (thread_dir / "thread.json").write_text(
        json.dumps(
            {
                "id": "thread-uuid",
                "process_id": "proc-uuid",
                "title": "Main Thread",
                "description": "Primary",
                "is_main": True,
                "created_at": "2025-01-02T01:00:00Z",
                "updated_at": "2025-01-02T02:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (thread_dir / "backlog" / "2025-01-02.md").write_text(
        """---
id: backlog-1
title: Backlog
created: 2025-01-02T02:30:00Z
updated: 2025-01-02T02:45:00Z
---

- update
""",
        encoding="utf-8",
    )

    (thread_dir / "OVERVIEW.md").write_text(
        """---
title: Overview
updated: 2025-01-02T02:10:00Z
---

# Overview
""",
        encoding="utf-8",
    )

    participants = {
        "version": 1,
        "thread_id": "thread-uuid",
        "process_slug": "demo",
        "updated_at": "2025-01-02T02:50:00Z",
        "participants": [],
    }
    (thread_dir / "participants.json").write_text(json.dumps(participants) + "\n", encoding="utf-8")

    return runtime_root


def test_process_adapter_lists_processes(tmp_path: Path) -> None:
    runtime_root = _make_runtime(tmp_path)
    adapter = ProcessFSAdapter(runtime_root)
    processes = adapter.list_processes()
    assert len(processes) == 1
    entry = processes[0]
    assert isinstance(entry, ProcessEntry)
    assert entry.slug == "demo"
    assert entry.thread_count == 1
    backlog = adapter.collect_backlog(entry)
    if backlog:
        event = backlog[0]
        assert isinstance(event, RuntimeEvent)
        assert event.event_type == "backlog"


def test_thread_adapter_roundtrip(tmp_path: Path) -> None:
    runtime_root = _make_runtime(tmp_path)
    adapter = ThreadFSAdapter(runtime_root)
    threads = adapter.list_threads()
    assert len(threads) == 1
    entry = threads[0]
    assert isinstance(entry, ThreadEntry)
    assert entry.thread_slug == "main"
    manifest = adapter.load_participants_manifest(entry)
    assert isinstance(manifest, ThreadParticipantsManifest)
    manifest.participants.append(
        ThreadParticipant(
            participant_id="agent-1",
            type=ThreadParticipantType.AGENT,
            role=ThreadParticipantRole.EXECUTOR,
            status=ThreadParticipantStatus.ATTACHED,
            identity=ThreadParticipantIdentityAgent(
                agent_process_thread_id=UUID("11111111-1111-1111-1111-111111111111"),
                agent_process_id=UUID("11111111-1111-1111-1111-111111111112"),
                agent_id=UUID("11111111-1111-1111-1111-111111111113"),
                identity_id=UUID("11111111-1111-1111-1111-111111111114"),
                actor_id=UUID("11111111-1111-1111-1111-111111111115"),
                slug="demo-agent/main/main",
            ),
        )
    )
    adapter.write_participants_manifest(entry, manifest)
    refreshed = adapter.load_participants_manifest(entry)
    assert len(refreshed.participants) == 1
