"""Kernel handlers for conversation operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple, Set
from uuid import uuid4

from aware_environment.fs import EnsureInstruction, OperationContext, OperationPlan

from .._shared.timeline import ensure_datetime
from ..thread.fs import ThreadFSAdapter
from .write_plan import (
    ConversationPlanResult,
    _conversation_dir,
    _conversation_path,
    _parse_document,
    _canonicalize_participants,
    plan_append_message,
    plan_create_conversation,
    plan_refresh_index,
    plan_repair_participants,
    plan_update_participants,
)
from .schemas import (
    ConversationDocumentPayload,
    ConversationHistoryPayload,
    ConversationListEntry,
    ConversationMetadata,
    ConversationMessage,
    ConversationParticipant,
    ConversationRepairResult,
)


@dataclass(frozen=True)
class ConversationRepairAggregateResult:
    """Aggregated repair response with the plans to execute."""

    plans: Tuple[OperationPlan, ...]
    payload: ConversationRepairResult


def _normalise_participants(participants: Iterable[Mapping[str, object]] | None) -> list[dict[str, object]]:
    if not participants:
        return []
    return [dict(entry) for entry in participants]


def _normalise_datetime(value: object | None, *, fallback: datetime | None = None) -> datetime:
    normalised = ensure_datetime(value)
    if normalised:
        return normalised
    if fallback:
        return fallback.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _isoformat(value: datetime | None) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalise_metadata_dates(metadata: dict[str, object]) -> None:
    for key in ("created_at", "updated_at"):
        value = metadata.get(key)
        dt = ensure_datetime(value)
        if dt:
            metadata[key] = _isoformat(dt)


def _split_message_segments(body: str) -> List[str]:
    if not body.strip():
        return []
    segments: List[str] = []
    current: List[str] = []
    for line in body.splitlines():
        if line.strip() == "---":
            if current and any(part.strip() for part in current):
                segments.append("\n".join(current).strip("\n"))
            current = []
        else:
            current.append(line)
    if current and any(part.strip() for part in current):
        segments.append("\n".join(current).strip("\n"))
    return segments


def _parse_message_segment(segment: str) -> Optional[dict[str, object]]:
    if not segment:
        return None
    lines = segment.splitlines()
    metadata: dict[str, object] = {}
    body_lines: List[str] = []
    in_body = False
    for line in lines:
        if not in_body and line.strip() == "":
            in_body = True
            continue
        if not in_body:
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip('"')
        else:
            body_lines.append(line)

    created = ensure_datetime(metadata.get("created_at"))
    metadata["created_at"] = _isoformat(created) if created else metadata.get("created_at")
    metadata.setdefault("message_id", metadata.get("message_id"))
    metadata.setdefault("receiver_id", metadata.get("receiver_id"))
    metadata.setdefault("message_type", metadata.get("message_type"))
    metadata.setdefault("status", metadata.get("status"))
    metadata.setdefault("actor_id", "")
    metadata["content"] = "\n".join(body_lines).strip()
    return metadata


def _load_conversation(runtime_root: Path, process_slug: str, thread_slug: str, conversation_slug: str) -> Tuple[Path, dict[str, object], str]:
    conversation_path = _conversation_path(runtime_root, process_slug, thread_slug, conversation_slug)
    if not conversation_path.exists():
        raise FileNotFoundError(f"Conversation '{process_slug}/{thread_slug}/{conversation_slug}' not found.")
    result = _parse_document(conversation_path)
    metadata = dict(result.metadata)
    _normalise_metadata_dates(metadata)
    metadata.setdefault("updated_at", metadata.get("created_at"))
    return conversation_path, metadata, result.body


def _load_index_entries(runtime_root: Path, process_slug: str, thread_slug: str) -> dict[str, dict[str, object]]:
    conversations_dir = _conversation_dir(runtime_root, process_slug, thread_slug)
    index_path = conversations_dir / ".index.json"
    if not index_path.exists():
        return {}
    try:
        index_data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    entries: dict[str, dict[str, object]] = {}
    for entry in index_data.get("entries", []):
        slug = entry.get("slug")
        if slug:
            entries[str(slug)] = entry
    return entries


def _build_list_entry(
    process_slug: str,
    thread_slug: str,
    path: Path,
    metadata: Mapping[str, object],
    index_entry: Optional[Mapping[str, object]],
) -> ConversationListEntry:
    participants = metadata.get("participants")
    participant_count = len(participants) if isinstance(participants, list) else 0
    return ConversationListEntry(
        id=f"{process_slug}/{thread_slug}/{path.stem}",
        uuid=metadata.get("conversation_id"),
        process_slug=process_slug,
        thread_slug=thread_slug,
        slug=path.stem,
        conversation_id=metadata.get("conversation_id"),
        title=metadata.get("title"),
        description=metadata.get("description"),
        created_at=metadata.get("created_at"),
        updated_at=metadata.get("updated_at"),
        participant_count=participant_count,
        path=path,
        index_entry=index_entry,
    )


def _split_thread_identifier(identifier: str) -> tuple[str, str]:
    value = (identifier or "").strip()
    if not value or "/" not in value:
        raise ValueError("Thread identifier must be '<process>/<thread>'.")
    process_slug, thread_slug = value.split("/", 1)
    return process_slug, thread_slug


def _collect_repair_entries(
    runtime_root: Path,
    process_slug: Optional[str],
    thread_slug: Optional[str],
    conversation_slug: Optional[str],
    *,
    limit: Optional[int] = None,
) -> list[ConversationListEntry]:
    runtime_root = Path(runtime_root).resolve()
    entries: list[ConversationListEntry] = []

    if conversation_slug and process_slug and thread_slug:
        identifier = f"{process_slug}/{thread_slug}/{conversation_slug}"
        entry = resolve(runtime_root, identifier=identifier)
        if isinstance(entry, ConversationListEntry):
            entries = [entry]
        else:
            entries = [ConversationListEntry.model_validate(entry)]  # type: ignore[attr-defined]
    elif process_slug and thread_slug:
        items = list_conversations(
            runtime_root,
            process_slug=process_slug,
            thread_slug=thread_slug,
        )
        entries = list(items)
    else:
        raise ValueError("Conversation repair requires process_slug and thread_slug selectors.")

    if limit is not None and limit >= 0:
        entries = entries[:limit]
    return entries


def create(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    title: str,
    description: str | None = None,
    participants: Iterable[Mapping[str, object]] | None = None,
    slug: str | None = None,
) -> ConversationPlanResult:
    return plan_create_conversation(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        title=title,
        description=description,
        participants=_normalise_participants(participants),
        slug=slug,
    )


def append(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    conversation_slug: str,
    actor_id: str,
    content: str,
    message_id: str | None = None,
    created_at: object | None = None,
    receiver_id: str | None = None,
    status: str | None = None,
    message_type: str | None = None,
) -> ConversationPlanResult:
    now = datetime.now(timezone.utc)
    message_identifier = message_id or str(uuid4())
    created_dt = _normalise_datetime(created_at, fallback=now)
    return plan_append_message(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        conversation_slug=conversation_slug,
        actor_id=actor_id,
        content=content,
        message_id=message_identifier,
        created_at=created_dt,
        receiver_id=receiver_id,
        status=status,
        message_type=message_type,
    )


def participants(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    conversation_slug: str,
    participants: Iterable[Mapping[str, object]],
) -> ConversationPlanResult:
    return plan_update_participants(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        conversation_slug=conversation_slug,
        participants=_normalise_participants(participants),
    )


def repair_participants(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    conversation_slug: str | None = None,
    dry_run: bool = False,
    limit: Optional[int] = None,
) -> ConversationRepairAggregateResult:
    runtime_root = Path(runtime_root).resolve()
    entries = _collect_repair_entries(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        conversation_slug=conversation_slug,
        limit=limit,
    )

    updated: list[str] = []
    skipped: list[str] = []
    plans: list[OperationPlan] = []

    for entry in entries:
        _, metadata, _ = _load_conversation(
            runtime_root,
            entry.process_slug,
            entry.thread_slug,
            entry.slug,
        )
        existing_participants_raw = metadata.get("participants") or []
        existing_models = [
            ConversationParticipant.model_validate(item) for item in existing_participants_raw
        ]
        existing_dump = [model.model_dump(mode="json") for model in existing_models]

        canonical_participants = _canonicalize_participants(
            runtime_root,
            entry.process_slug,
            entry.thread_slug,
            existing_dump,
        )
        canonical_models = [
            ConversationParticipant.model_validate(participant) for participant in canonical_participants
        ]
        canonical_dump = [model.model_dump(mode="json") for model in canonical_models]

        if existing_dump == canonical_dump:
            skipped.append(entry.slug)
            continue

        updated.append(entry.slug)
        if dry_run:
            continue

        plan_result = plan_repair_participants(
            runtime_root,
            process_slug=entry.process_slug,
            thread_slug=entry.thread_slug,
            conversation_slug=entry.slug,
            participants=canonical_participants,
        )
        plans.append(plan_result.plan)

    payload = ConversationRepairResult(
        updated=len(updated),
        skipped=len(skipped),
        dry_run=dry_run,
        conversations=updated,
        skipped_conversations=skipped,
    )
    return ConversationRepairAggregateResult(plans=tuple(plans), payload=payload)


def index_refresh(
    runtime_root: Path,
    *,
    targets: Sequence[tuple[str, str]],
) -> ConversationPlanResult:
    return plan_refresh_index(runtime_root, targets=targets)


def history(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    conversation_slug: str,
    since: object | None = None,
    limit: Optional[int] = None,
    format: str | None = None,
) -> ConversationHistoryPayload:
    conversation_path, metadata, body = _load_conversation(runtime_root, process_slug, thread_slug, conversation_slug)

    since_dt = ensure_datetime(since)
    messages: List[dict[str, object]] = []
    for segment in _split_message_segments(body):
        message = _parse_message_segment(segment)
        if message is None:
            continue
        created = ensure_datetime(message.get("created_at"))
        if since_dt and created and created <= since_dt:
            continue
        if created:
            message["created_at"] = _isoformat(created)
        messages.append(message)

    if limit and limit > 0:
        messages = messages[-limit:]

    metadata_model = ConversationMetadata.model_validate(metadata)
    message_models = [ConversationMessage.model_validate(message) for message in messages]
    return ConversationHistoryPayload(
        conversation=f"{process_slug}/{thread_slug}/{conversation_slug}",
        metadata=metadata_model,
        messages=message_models,
        path=conversation_path,
        markdown=body,
    )


def document(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    conversation_slug: str,
    format: str | None = None,
) -> ConversationDocumentPayload:
    conversation_path, metadata, body = _load_conversation(runtime_root, process_slug, thread_slug, conversation_slug)
    metadata_model = ConversationMetadata.model_validate(metadata)
    return ConversationDocumentPayload(
        metadata=metadata_model,
        body=body,
        path=conversation_path,
    )


def list_conversations(
    runtime_root: Path,
    *,
    process_slug: str | None = None,
    thread_slug: str | None = None,
    thread: str | None = None,
    since: object | None = None,
) -> List[ConversationListEntry]:
    runtime_root = Path(runtime_root).resolve()
    if thread and (not process_slug or not thread_slug):
        process_slug, thread_slug = _split_thread_identifier(thread)
    if not process_slug or not thread_slug:
        raise ValueError("Both process_slug and thread_slug must be provided.")

    conversations_dir = _conversation_dir(runtime_root, process_slug, thread_slug)
    if not conversations_dir.exists():
        return []

    since_dt = ensure_datetime(since)
    index_entries = _load_index_entries(runtime_root, process_slug, thread_slug)
    entries: List[ConversationListEntry] = []
    for path in sorted(conversations_dir.glob("*.md")):
        result = _parse_document(path)
        metadata = dict(result.metadata)
        _normalise_metadata_dates(metadata)
        updated = ensure_datetime(metadata.get("updated_at") or metadata.get("created_at"))
        if since_dt and updated and updated <= since_dt:
            continue
        entry = _build_list_entry(process_slug, thread_slug, path, metadata, index_entries.get(path.stem))
        entries.append(entry)

    entries.sort(
        key=lambda item: ensure_datetime(item.updated_at) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return entries


def resolve(
    runtime_root: Path,
    *,
    identifier: str,
) -> ConversationListEntry:
    runtime_root = Path(runtime_root).resolve()
    identifier = identifier.strip()
    if not identifier:
        raise ValueError("Conversation identifier must be provided.")

    parts = identifier.split("/")
    if len(parts) == 3:
        process_slug, thread_slug, conversation_slug = parts
        conversation_path = _conversation_path(runtime_root, process_slug, thread_slug, conversation_slug)
        if not conversation_path.exists():
            raise FileNotFoundError(f"Conversation '{identifier}' not found.")
        metadata_result = _parse_document(conversation_path)
        metadata = dict(metadata_result.metadata)
        _normalise_metadata_dates(metadata)
        metadata.setdefault("updated_at", metadata.get("created_at"))
        index_entries = _load_index_entries(runtime_root, process_slug, thread_slug)
        return _build_list_entry(process_slug, thread_slug, conversation_path, metadata, index_entries.get(conversation_path.stem))

    identifier_lower = identifier.lower()
    for process_dir in sorted(runtime_root.iterdir()):
        if not process_dir.is_dir():
            continue
        threads_dir = process_dir / "threads"
        if not threads_dir.exists():
            continue
        process_slug = process_dir.name
        for thread_dir in sorted(threads_dir.iterdir()):
            if not thread_dir.is_dir():
                continue
            conversations_dir = thread_dir / "conversations"
            if not conversations_dir.exists():
                continue
            thread_slug = thread_dir.name
            index_entries = _load_index_entries(runtime_root, process_slug, thread_slug)
            for path in sorted(conversations_dir.glob("*.md")):
                result = _parse_document(path)
                metadata = dict(result.metadata)
                conversation_id = str(metadata.get("conversation_id") or "").strip().lower()
                if conversation_id and conversation_id == identifier_lower:
                    _normalise_metadata_dates(metadata)
                    metadata.setdefault("updated_at", metadata.get("created_at"))
                    return _build_list_entry(process_slug, thread_slug, path, metadata, index_entries.get(path.stem))

    raise FileNotFoundError(f"Conversation '{identifier}' not found.")


__all__ = [
    "append",
    "create",
    "document",
    "history",
    "index_refresh",
    "list_conversations",
    "participants",
    "repair_participants",
    "resolve",
]
