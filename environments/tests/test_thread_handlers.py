from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID
from pathlib import Path
from typing import Iterator

import pytest
from aware_environment.fs import apply_plan

from aware_environments.kernel.objects.thread import handlers as thread_handlers
from aware_environments.kernel.objects.thread.fs import ThreadFSAdapter
from aware_environments.kernel.objects.thread.schemas import (
    ThreadParticipant,
    ThreadParticipantIdentityAgent,
    ThreadParticipantRole,
    ThreadParticipantType,
    ThreadParticipantSession,
    ThreadParticipantSessionState,
    ThreadParticipantStatus,
    ThreadParticipantsManifest,
)


APT_UUID = "11111111-1111-1111-1111-111111111111"
PROCESS_UUID = "22222222-2222-2222-2222-222222222222"
AGENT_UUID = "33333333-3333-3333-3333-333333333333"
IDENTITY_UUID = "44444444-4444-4444-4444-444444444444"
ACTOR_UUID = "55555555-5555-5555-5555-555555555555"


@pytest.fixture()
def runtime_root(tmp_path: Path) -> Iterator[Path]:
    docs_root = tmp_path / "docs"
    root = docs_root / "runtime" / "process"
    thread_dir = root / "demo-process" / "threads" / "main"
    (thread_dir / "branches").mkdir(parents=True, exist_ok=True)
    (thread_dir / "pane_manifests").mkdir(parents=True, exist_ok=True)
    (thread_dir / "backlog").mkdir(parents=True, exist_ok=True)

    thread_json = {
        "id": APT_UUID,
        "process_id": PROCESS_UUID,
        "thread_slug": "main",
        "title": "Main Thread",
        "thread_task_list": [],
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T01:00:00Z",
    }
    (thread_dir / "thread.json").write_text(json.dumps(thread_json, indent=2) + "\n", encoding="utf-8")

    backlog_entry = thread_dir / "backlog" / "2025-10-01-first.md"
    backlog_entry.write_text(
        "---\ntitle: First Event\ncreated: 2025-10-01T10:00:00Z\nupdated: 2025-10-01T10:00:00Z\n---\n\nEntry body\n",
        encoding="utf-8",
    )

    branch_payload = {
        "branch_id": "task-branch",
        "id": "task-branch",
        "pane_kind": "task",
        "name": "Task Pane",
        "is_main": False,
        "created_at": "2025-10-01T10:00:00Z",
        "updated_at": "2025-10-01T10:00:00Z",
    }
    pane_manifest = {
        "pane_kind": "task",
        "branch_id": "task-branch",
        "manifest_version": 1,
        "payload": {
            "task_id": "task-123",
            "task_manifest_path": "docs/projects/demo/tasks/sample/OVERVIEW.md",
        },
    }
    legacy_branch_file = thread_dir / "branches" / "task.json"
    legacy_branch_file.write_text(json.dumps(branch_payload, indent=2) + "\n", encoding="utf-8")
    legacy_manifest_file = thread_dir / "pane_manifests" / "task.json"
    legacy_manifest_file.write_text(json.dumps(pane_manifest, indent=2) + "\n", encoding="utf-8")

    projects_root = docs_root / "projects"
    task_dir = projects_root / "sample-project" / "tasks" / "task-alpha"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "OVERVIEW.md").write_text(
        "# Task Alpha\n\nStatus: running\n",
        encoding="utf-8",
    )
    index_payload = [
        {
            "task_id": "59f06ded-ab8c-51aa-95f1-f93bbd50c9a1",
            "slug": "task-alpha",
            "status": "running",
            "manifest_path": "docs/projects/sample-project/tasks/task-alpha/OVERVIEW.md",
            "directories": {
                "task_root": "docs/projects/sample-project/tasks/task-alpha",
                "overview": "docs/projects/sample-project/tasks/task-alpha/OVERVIEW.md",
            },
            "repository_id": "47db3d7384faf00c5948a1f3f1106a58be46fe0ca90ade6129b463362a7f3b14",
            "repository_root_path": ".",
            "paths": [
                {
                    "key": "task-root",
                    "path": "docs/projects/sample-project/tasks/task-alpha",
                    "is_root": True,
                },
                {
                    "key": "overview",
                    "path": "docs/projects/sample-project/tasks/task-alpha/OVERVIEW.md",
                    "is_root": False,
                },
                {
                    "key": "manifest",
                    "path": "docs/projects/sample-project/tasks/task-alpha/OVERVIEW.md",
                    "is_root": False,
                },
            ],
            "hash": "af63f828b7107e2e3096600e6ca8418785d3f42467519b2d61c6c8047765e1fd",
            "metadata": {
                "status": "running",
                "priority": "medium",
                "storage_mode": "filesystem",
            },
            "updated_at": "2025-11-04T00:00:00Z",
        }
    ]
    index_path = task_dir.parent / ".index.json"
    index_path.write_text(json.dumps(index_payload, indent=2) + "\n", encoding="utf-8")

    adapter = ThreadFSAdapter(root)
    entry = adapter.get_thread("demo-process/main")
    assert entry is not None

    manifest = ThreadParticipantsManifest(
        version=1,
        thread_id=APT_UUID,
        process_slug="demo-process",
        updated_at=datetime.now(timezone.utc),
        participants=[
            ThreadParticipant(
                participant_id="participant-1",
                type=ThreadParticipantType.AGENT,
                status=ThreadParticipantStatus.ATTACHED,
                role=ThreadParticipantRole.EXECUTOR,
                identity=ThreadParticipantIdentityAgent(
                    agent_process_thread_id=UUID(APT_UUID),
                    agent_process_id=UUID(PROCESS_UUID),
                    agent_id=UUID(AGENT_UUID),
                    identity_id=UUID(IDENTITY_UUID),
                    actor_id=UUID(ACTOR_UUID),
                    slug="demo-agent/main/main",
                ),
                session=ThreadParticipantSession(
                    session_id="session-uuid",
                    state=ThreadParticipantSessionState.RUNNING,
                    transport="pty",
                    daemon_pid=None,
                ),
                metadata={"provider": "codex"},
            )
        ],
    )
    adapter.write_participants_manifest(entry, manifest)

    yield root


def test_thread_status_handler(runtime_root: Path) -> None:
    payload = thread_handlers.thread_status_handler(runtime_root, process="demo-process", thread="main")
    assert payload["process_slug"] == "demo-process"
    assert payload["thread_slug"] == "main"
    assert payload["branch_count"] == 1
    assert payload["branches"][0]["pane_kind"] == "task"


def test_thread_pane_manifest_handler(runtime_root: Path) -> None:
    payload = thread_handlers.thread_pane_manifest_handler(
        runtime_root,
        process="demo-process",
        thread="main",
        pane="task",
        branch_id="task-branch",
    )
    assert payload["branch"]["branch_id"] == "task-branch"
    assert payload["pane_manifest"]["payload"]["task_id"] == "task-123"


def test_thread_backlog_handler(runtime_root: Path) -> None:
    entries = thread_handlers.thread_backlog_handler(runtime_root, process="demo-process", thread="main")
    assert entries
    entry = entries[0]
    assert entry["event_type"] == "backlog"
    assert entry["summary"] == "First Event"


def test_thread_list_handler(runtime_root: Path) -> None:
    payload = thread_handlers.thread_list_handler(runtime_root, process="demo-process")
    assert payload
    assert payload[0]["thread_slug"] == "main"


def test_thread_participants_list_handler(runtime_root: Path) -> None:
    participants = thread_handlers.thread_participants_list_handler(
        runtime_root,
        process="demo-process",
        thread="main",
    )
    assert isinstance(participants, list)
    assert participants[0]["participant_id"] == "participant-1"
    assert participants[0]["metadata"]["provider"] == "codex"


def _apply_plans(result) -> None:
    plans = getattr(result, "plans", None)
    if plans is None:
        plan = getattr(result, "plan", None)
        if plan is None:
            return []
        plans = (plan,)
    receipts = []
    for plan in plans:
        receipts.append(apply_plan(plan))
    return receipts


def test_thread_branch_set_and_refresh(runtime_root: Path) -> None:
    result = thread_handlers.thread_branch_set_handler(
        runtime_root,
        process="demo-process",
        thread="main",
        pane="analysis",
        branch={"name": "Analysis Pane"},
        pane_manifest={"payload": {"notes": "initial"}},
        manifest_version=2,
        task_binding={"task_id": "task-999", "task_slug": "analysis/task-999", "project_slug": "analysis"},
    )
    _apply_plans(result)

    entry_dir = runtime_root / "demo-process" / "threads" / "main"
    branch_path = entry_dir / result.payload["branch_path"]
    manifest_path = entry_dir / result.payload["pane_manifest_path"]

    branch_data = json.loads(branch_path.read_text(encoding="utf-8"))
    pane_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert branch_data["pane_kind"] == "analysis"
    assert pane_manifest["manifest_version"] == 2

    refresh = thread_handlers.thread_branch_refresh_handler(
        runtime_root,
        process="demo-process",
        thread="main",
        pane="analysis",
        branch_id=branch_data["branch_id"],
    )
    _apply_plans(refresh)

    refreshed_branch = json.loads(branch_path.read_text(encoding="utf-8"))
    assert refreshed_branch["updated_at"]


def test_thread_branch_set_with_task(runtime_root: Path) -> None:
    projects_root = runtime_root.parents[1] / "projects"
    result = thread_handlers.thread_branch_set_handler(
        runtime_root,
        process="demo-process",
        thread="main",
        pane="task",
        branch=None,
        pane_manifest=None,
        manifest_version=1,
        task_binding=None,
        task="sample-project/task-alpha",
        projects_root=str(projects_root),
    )
    _apply_plans(result)

    entry_dir = runtime_root / "demo-process" / "threads" / "main"
    branch_path = entry_dir / result.payload["branch_path"]
    manifest_path = entry_dir / result.payload["pane_manifest_path"]

    branch_data = json.loads(branch_path.read_text(encoding="utf-8"))
    pane_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert branch_data["pane_kind"] == "task"
    assert pane_manifest["payload"]["task_id"] == "59f06ded-ab8c-51aa-95f1-f93bbd50c9a1"
    assert pane_manifest["payload"]["status"] == "running"


def test_thread_branch_migrate_singleton(runtime_root: Path) -> None:
    result = thread_handlers.thread_branch_migrate_handler(
        runtime_root,
        process="demo-process",
        thread="main",
        pane="task",
        migrate_singleton=True,
    )
    assert result.plans
    plan = result.plans[0]
    assert plan.moves
    receipts = _apply_plans(result)
    assert receipts
    receipt_ops = receipts[0].fs_ops
    move_ops = [op for op in receipt_ops if getattr(op, "type", None) == "move"]
    assert any(str(op.src).endswith("branches/task.json") for op in move_ops)
    assert any("/branches/task/" in str(op.dest) for op in move_ops)

    entry_dir = runtime_root / "demo-process" / "threads" / "main"
    branch_paths = list((entry_dir / "branches").rglob("*.json"))
    assert any("task" in path.parts and path.parent.name == "task" for path in branch_paths)
    legacy_branch = entry_dir / "branches" / "task.json"
    assert not legacy_branch.exists()


def test_thread_participants_bind_and_update(runtime_root: Path) -> None:
    participant = {
        "participant_id": "participant-2",
        "type": "agent",
        "role": "executor",
        "status": "attached",
        "identity": {
            "type": "agent",
            "agent_process_thread_id": APT_UUID,
            "agent_process_id": PROCESS_UUID,
            "agent_id": AGENT_UUID,
            "identity_id": IDENTITY_UUID,
            "actor_id": ACTOR_UUID,
            "slug": "demo-agent/main/main",
        },
        "metadata": {"provider": "codex"},
    }

    result = thread_handlers.thread_participants_bind_handler(
        runtime_root,
        process="demo-process",
        thread="main",
        participant=participant,
        force=False,
    )
    _apply_plans(result)

    manifest_path = runtime_root / "demo-process" / "threads" / "main" / "participants.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    participants = manifest_data.get("participants", [])
    assert any(entry.get("participant_id") == "participant-2" for entry in participants)

    updates = {
        "status": "detached",
        "session": {"state": "stopped"},
        "metadata": {"provider": "codex", "note": "updated"},
    }
    update_result = thread_handlers.thread_participants_update_handler(
        runtime_root,
        process="demo-process",
        thread="main",
        participant_id="participant-2",
        updates=updates,
    )
    _apply_plans(update_result)

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    updated = next(
        entry for entry in manifest_data.get("participants", []) if entry.get("participant_id") == "participant-2"
    )
    assert updated["status"] == "detached"
    assert updated["metadata"]["note"] == "updated"
