from __future__ import annotations

import json
import yaml
from datetime import datetime, timezone
from pathlib import Path

from aware_environment.fs import apply_plan
from aware_environment.fs.receipt import Receipt, WriteOp
from aware_environments.kernel.objects.conversation import handlers as conversation_handlers
from aware_environments.kernel.objects.conversation.schemas import (
    ConversationAppendResult,
    ConversationHistoryPayload,
    ConversationIndexRefreshResult,
    ConversationListEntry,
    ConversationParticipantsResult,
)
from aware_environments.kernel.objects._shared.frontmatter import load_frontmatter


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _bootstrap_thread(runtime_root: Path, *, process_slug: str, thread_slug: str) -> Path:
    process_dir = runtime_root / process_slug
    thread_dir = process_dir / "threads" / thread_slug
    thread_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        process_dir / "process.json",
        {
            "id": "proc-uuid-1234",
            "title": "Demo Process",
            "status": "active",
            "created_at": "2025-10-12T10:00:00Z",
            "updated_at": "2025-10-12T12:00:00Z",
        },
    )
    (process_dir / "backlog").mkdir(exist_ok=True)

    _write_json(
        thread_dir / "thread.json",
        {
            "id": f"{thread_slug}-uuid-5678",
            "process_id": "proc-uuid-1234",
            "title": "Demo Thread",
            "is_main": True,
            "created_at": "2025-10-12T10:05:00Z",
            "updated_at": "2025-10-12T12:05:00Z",
        },
    )
    (thread_dir / "backlog").mkdir(exist_ok=True)
    _write_json(
        thread_dir / "participants.json",
        {
            "version": 1,
            "thread_id": f"{thread_slug}-uuid-5678",
            "process_slug": process_slug,
            "updated_at": "2025-10-12T12:00:00Z",
            "participants": [
                {
                    "participant_id": "apt-agent",
                    "type": "agent",
                    "role": "executor",
                    "status": "attached",
                    "identity": {
                        "type": "agent",
                        "agent_process_thread_id": "00000000-0000-0000-0000-000000000001",
                        "agent_process_id": "00000000-0000-0000-0000-000000000002",
                        "agent_id": "00000000-0000-0000-0000-000000000003",
                        "identity_id": "00000000-0000-0000-0000-000000000004",
                        "actor_id": "11111111-1111-1111-1111-111111111111",
                        "slug": "apt-agent",
                    },
                    "metadata": {"handle": "@agent"},
                }
            ],
        },
    )
    pane_dir = thread_dir / "pane_manifests"
    pane_dir.mkdir(exist_ok=True)
    _write_json(
        pane_dir / "code_editor.json",
        {"manifest_version": 1, "pane_kind": "code_editor", "branch_id": "branch-uuid"},
    )
    return thread_dir


def _bootstrap_runtime(tmp_path: Path) -> tuple[Path, str, str]:
    runtime_root = tmp_path / "docs" / "runtime" / "process"
    process_slug = "demo-process"
    thread_slug = "main-thread"
    _bootstrap_thread(runtime_root, process_slug=process_slug, thread_slug=thread_slug)
    return runtime_root, process_slug, thread_slug


def _write_conversation_document(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    slug: str,
    participants: list[dict[str, object]],
) -> Path:
    conversations_dir = runtime_root / process_slug / "threads" / thread_slug / "conversations"
    conversations_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "conversation_id": f"{slug}-uuid",
        "title": "Demo Conversation",
        "created_at": "2025-10-12T12:00:00Z",
        "updated_at": "2025-10-12T12:05:00Z",
        "participants": participants,
    }
    frontmatter = yaml.safe_dump(metadata, sort_keys=False).strip()
    path = conversations_dir / f"{slug}.md"
    content = f"---\n{frontmatter}\n---\n\n# Conversation\n\nOriginal entry\n"
    path.write_text(content, encoding="utf-8")
    return path


def _apply_plan(result) -> Receipt:
    receipt = apply_plan(result.plan)
    assert isinstance(receipt, Receipt)
    return receipt


def test_create_conversation_plan(tmp_path: Path) -> None:
    runtime_root, process_slug, thread_slug = _bootstrap_runtime(tmp_path)

    result = conversation_handlers.create(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        title="Demo Conversation",
        description="Initial discussion",
        participants=[
            {
                "id": "apt-agent",
                "actor_id": "11111111-1111-1111-1111-111111111111",
                "type": "agent",
                "role": "executor",
                "handle": "@agent",
            }
        ],
    )
    assert isinstance(result.payload, ConversationListEntry)

    receipt = _apply_plan(result)
    assert any(
        isinstance(op, WriteOp) and op.doc_type == "conversation-doc" for op in receipt.fs_ops
    )
    slug = result.payload.slug
    conversation_path = runtime_root / process_slug / "threads" / thread_slug / "conversations" / f"{slug}.md"
    assert conversation_path.exists()

    fm = load_frontmatter(conversation_path)
    assert fm.metadata["title"] == "Demo Conversation"
    assert fm.metadata["participants"][0]["handle"] == "@agent"

    index_path = conversation_path.parent / ".index.json"
    assert index_path.exists()
    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    assert index_data["entries"]


def test_append_and_history(tmp_path: Path) -> None:
    runtime_root, process_slug, thread_slug = _bootstrap_runtime(tmp_path)
    create_result = conversation_handlers.create(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        title="Session",
        participants=[],
    )
    _apply_plan(create_result)
    slug = create_result.payload.slug

    append_result = conversation_handlers.append(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        conversation_slug=slug,
        actor_id="11111111-1111-1111-1111-111111111111",
        content="Hello kernel!",
        message_id="msg-001",
        created_at=datetime(2025, 10, 12, 12, 30, tzinfo=timezone.utc),
        receiver_id=None,
        status="active",
        message_type="standard",
    )
    assert isinstance(append_result.payload, ConversationAppendResult)
    receipt = _apply_plan(append_result)
    assert any(
        isinstance(op, WriteOp) and op.doc_type == "conversation-doc" for op in receipt.fs_ops
    )

    history = conversation_handlers.history(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        conversation_slug=slug,
    )
    assert isinstance(history, ConversationHistoryPayload)
    assert history.messages
    messages = [msg for msg in history.messages if msg.message_id]
    assert any(msg.message_id == "msg-001" for msg in messages)
    message = next(msg for msg in messages if msg.message_id == "msg-001")
    assert message.message_type == "standard"

    document = conversation_handlers.document(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        conversation_slug=slug,
    )
    assert "Hello kernel!" in document.body


def test_participants_update_and_resolve(tmp_path: Path) -> None:
    runtime_root, process_slug, thread_slug = _bootstrap_runtime(tmp_path)
    create_result = conversation_handlers.create(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        title="Session",
        participants=[],
    )
    _apply_plan(create_result)
    slug = create_result.payload.slug

    participants_result = conversation_handlers.participants(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        conversation_slug=slug,
        participants=[
            {
                "id": "apt-human",
                "actor_id": "22222222-2222-2222-2222-222222222222",
                "type": "human",
                "role": "viewer",
                "handle": "@human",
            }
        ],
    )
    assert isinstance(participants_result.payload, ConversationParticipantsResult)
    plan = participants_result.plan
    assert not plan.writes
    assert len(plan.patches) >= 1
    receipt = _apply_plan(participants_result)
    assert any(
        isinstance(op, WriteOp) and op.doc_type == "conversation-doc" for op in receipt.fs_ops
    )

    resolved = conversation_handlers.resolve(
        runtime_root,
        identifier=f"{process_slug}/{thread_slug}/{slug}",
    )
    assert resolved.participant_count == 1
    convo_id = resolved.conversation_id
    resolved_by_id = conversation_handlers.resolve(runtime_root, identifier=convo_id)
    assert resolved_by_id.slug == slug


def test_list_conversations_and_since_filter(tmp_path: Path) -> None:
    runtime_root, process_slug, thread_slug = _bootstrap_runtime(tmp_path)
    create_result = conversation_handlers.create(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        title="Session",
        participants=[],
    )
    _apply_plan(create_result)
    slug = create_result.payload.slug

    entries = conversation_handlers.list_conversations(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
    )
    assert entries and any(entry.slug == slug for entry in entries)
    first_entry = entries[0]
    assert first_entry.index_entry is not None
    assert first_entry.index_entry.get("slug") == first_entry.slug

    since = datetime.now(timezone.utc)
    filtered = conversation_handlers.list_conversations(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        since=since,
    )
    assert filtered == []


def test_list_conversations_with_thread_identifier(tmp_path: Path) -> None:
    runtime_root, process_slug, thread_slug = _bootstrap_runtime(tmp_path)
    create_result = conversation_handlers.create(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        title="Session",
        participants=[],
    )
    _apply_plan(create_result)

    entries = conversation_handlers.list_conversations(
        runtime_root,
        thread=f"{process_slug}/{thread_slug}",
    )
    assert entries and entries[0].process_slug == process_slug


def test_index_refresh_plan(tmp_path: Path) -> None:
    runtime_root, process_slug, thread_slug = _bootstrap_runtime(tmp_path)
    create_one = conversation_handlers.create(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        title="Primary",
        participants=[],
    )
    _apply_plan(create_one)
    slug = create_one.payload.slug

    conversation_path = runtime_root / process_slug / "threads" / thread_slug / "conversations" / f"{slug}.md"
    text = conversation_path.read_text(encoding="utf-8")
    conversation_path.write_text(text.replace("Primary", "Primary Updated"), encoding="utf-8")

    refresh = conversation_handlers.index_refresh(
        runtime_root,
        targets=[(process_slug, thread_slug)],
    )
    assert isinstance(refresh.payload, ConversationIndexRefreshResult)
    plan = refresh.plan
    assert not plan.writes
    assert len(plan.patches) >= 1
    receipt = _apply_plan(refresh)
    index_path = runtime_root / process_slug / "threads" / thread_slug / "conversations" / ".index.json"
    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    assert any(entry["title"] == "Primary Updated" for entry in index_data.get("entries", []))


def test_repair_participants_plan_applies_changes(tmp_path: Path) -> None:
    runtime_root, process_slug, thread_slug = _bootstrap_runtime(tmp_path)
    slug = "alias-convo"
    conversation_path = _write_conversation_document(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        slug=slug,
        participants=[
            {
                "id": "apt-agent",
                "type": "agent",
                "role": "executor",
                "name": "Alias User",
                "handle": "@alias",
            }
        ],
    )

    result = conversation_handlers.repair_participants(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
    )
    assert result.payload.updated == 1
    assert result.payload.dry_run is False
    assert result.payload.conversations == [slug]
    assert len(result.plans) == 1

    receipt = apply_plan(result.plans[0])
    assert isinstance(receipt, Receipt)
    participants = load_frontmatter(conversation_path).metadata.get("participants") or []
    assert participants
    participant = participants[0]
    assert participant["actor_id"] == "11111111-1111-1111-1111-111111111111"
    assert participant["id"] == "11111111-1111-1111-1111-111111111111"
    assert participant.get("source_id") is None
    assert participant.get("handle") == "@alias"


def test_repair_participants_dry_run_no_changes(tmp_path: Path) -> None:
    runtime_root, process_slug, thread_slug = _bootstrap_runtime(tmp_path)
    slug = "dry-run-convo"
    conversation_path = _write_conversation_document(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        slug=slug,
        participants=[
            {
                "id": "apt-agent",
                "type": "agent",
                "role": "executor",
                "name": "Alias User",
                "handle": "@alias",
            }
        ],
    )
    baseline = conversation_path.read_text(encoding="utf-8")

    result = conversation_handlers.repair_participants(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        dry_run=True,
    )
    assert result.payload.dry_run is True
    assert result.payload.updated == 1
    assert result.plans == ()
    assert conversation_path.read_text(encoding="utf-8") == baseline
