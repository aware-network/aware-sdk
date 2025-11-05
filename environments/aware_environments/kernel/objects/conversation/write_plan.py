"""OperationPlan builders for conversation workflows."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from uuid import UUID, uuid4

import yaml

from aware_environment.fs import (
    EnsureInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    PatchInstruction,
    WriteInstruction,
)

from .._shared.frontmatter import load_frontmatter, FrontmatterResult
from .._shared.patch import build_patch_instruction_from_text
from ..thread.fs import ThreadFSAdapter
from ..thread.schemas import ThreadParticipant
from .schemas import (
    ConversationAppendResult,
    ConversationIndexRefreshResult,
    ConversationIndexRefreshThread,
    ConversationListEntry,
    ConversationParticipant,
    ConversationParticipantsResult,
)


def _iso_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _conversation_dir(runtime_root: Path, process_slug: str, thread_slug: str) -> Path:
    return Path(runtime_root) / process_slug / "threads" / thread_slug / "conversations"


def _conversation_path(runtime_root: Path, process_slug: str, thread_slug: str, slug: str) -> Path:
    stem = slug if slug.endswith(".md") else f"{slug}.md"
    return _conversation_dir(runtime_root, process_slug, thread_slug) / stem


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "conversation"


def _sanitize_message_body(content: str) -> str:
    # Preserve existing formatting while trimming trailing whitespace
    return content.rstrip()


def _build_message_block(metadata: Mapping[str, object], content: str) -> str:
    lines: list[str] = ["---"]
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, list):
            serialised = json.dumps(value, ensure_ascii=False)
            lines.append(f"{key}: {serialised}")
        else:
            lines.append(f'{key}: "{value}"')
    lines.append("---")
    body = _sanitize_message_body(content)
    return "\n".join(lines + ([body] if body else []))


def _message_metadata(
    *,
    message_id: str,
    actor_id: str,
    created_at: datetime,
    receiver_id: str | None,
    status: str | None,
    message_type: str | None,
) -> dict[str, object]:
    meta: dict[str, object] = {
        "message_id": message_id,
        "actor_id": actor_id,
        "created_at": _isoformat(created_at),
    }
    if receiver_id:
        meta["receiver_id"] = receiver_id
    if status:
        meta["status"] = status
    if message_type:
        meta["message_type"] = message_type
    return meta


def _compose_document(metadata: dict[str, object], body: str) -> str:
    header = yaml.safe_dump(metadata, sort_keys=False).strip()
    text = f"---\n{header}\n---\n"
    if body:
        text += "\n" + body.rstrip() + "\n"
    else:
        text += "\n"
    return text


def _parse_document(path: Path) -> FrontmatterResult:
    return load_frontmatter(path)


def _count_messages(body: str) -> int:
    if not body.strip():
        return 0
    segments = body.split("\n---\n")
    return sum(1 for segment in segments if segment.strip())


def _document_hash(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _thread_entry(runtime_root: Path, process_slug: str, thread_slug: str):
    adapter = ThreadFSAdapter(runtime_root)
    return adapter.get_thread(f"{process_slug}/{thread_slug}")


def _relativize(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _repo_root(runtime_root: Path) -> Path:
    try:
        return Path(runtime_root).resolve().parents[2]
    except IndexError:
        return Path(runtime_root).resolve()


def _participants_count(metadata: Mapping[str, object]) -> int:
    participants = metadata.get("participants")
    if isinstance(participants, list):
        return len(participants)
    return 0


def _normalise_metadata_dates(metadata: dict[str, object]) -> None:
    for key in ("created_at", "updated_at"):
        value = metadata.get(key)
        if isinstance(value, datetime):
            metadata[key] = _isoformat(value)


def _ensure_created(metadata: dict[str, object], created_at: datetime) -> None:
    metadata.setdefault("created_at", _isoformat(created_at))


def _ensure_title(metadata: dict[str, object], title: str | None, slug: str) -> None:
    if title:
        metadata["title"] = title
    else:
        metadata.setdefault("title", slug.replace("-", " ").title())


def _serialise_participants(participants: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    serialised: list[dict[str, object]] = []
    for entry in participants:
        serialised.append({key: value for key, value in entry.items() if value is not None})
    return serialised


def _normalize_uuid(value: object | None) -> Optional[str]:
    if value is None:
        return None
    try:
        return str(UUID(str(value).strip())).lower()
    except (ValueError, TypeError, AttributeError):
        value_str = str(value).strip()
        return value_str.lower() if value_str else None


def _participant_to_dict(participant: Mapping[str, object] | ConversationParticipant) -> dict[str, object]:
    if isinstance(participant, ConversationParticipant):
        return participant.model_dump(mode="json")
    if isinstance(participant, Mapping):
        return dict(participant)
    return dict(participant)


def _canonicalize_participants(
    runtime_root: Path,
    process_slug: str,
    thread_slug: str,
    participants: Sequence[Mapping[str, object] | ConversationParticipant],
) -> list[dict[str, object]]:
    participants = [_participant_to_dict(participant) for participant in participants]
    adapter = ThreadFSAdapter(runtime_root)
    entry = adapter.get_thread(f"{process_slug}/{thread_slug}")
    if entry is None:
        return [dict(participant) for participant in participants]

    manifest = adapter.load_participants_manifest(entry)
    alias_map: dict[str, ThreadParticipant] = {}
    actor_map: dict[str, ThreadParticipant] = {}

    for manifest_participant in manifest.participants:
        alias = manifest_participant.participant_id.strip().lower()
        alias_map[alias] = manifest_participant
        metadata_handle = (manifest_participant.metadata or {}).get("handle")
        if metadata_handle:
            alias_map.setdefault(metadata_handle.strip().lower(), manifest_participant)
        identity = getattr(manifest_participant.identity, "actor_id", None)
        if identity:
            actor_map[str(identity).lower()] = manifest_participant

    resolved: list[dict[str, object]] = []
    for entry_data in participants:
        data = dict(entry_data)
        actor_id = _normalize_uuid(data.get("actor_id") or data.get("id"))
        manifest_entry: Optional[ThreadParticipant] = None
        if actor_id and actor_id in actor_map:
            manifest_entry = actor_map[actor_id]
        else:
            for key in ("source_id", "id", "handle"):
                value = data.get(key)
                if not value:
                    continue
                alias_key = str(value).strip().lower()
                if alias_key and alias_key in alias_map:
                    manifest_entry = alias_map[alias_key]
                    break

        if manifest_entry:
            canonical_actor_id = _normalize_uuid(
                getattr(manifest_entry.identity, "actor_id", None) or manifest_entry.participant_id
            )
            data["actor_id"] = canonical_actor_id
            data["id"] = canonical_actor_id
            participant_type = (
                manifest_entry.type.value if hasattr(manifest_entry.type, "value") else str(manifest_entry.type)
            )
            participant_role = (
                manifest_entry.role.value if hasattr(manifest_entry.role, "value") else str(manifest_entry.role)
            )
            if participant_type:
                data.setdefault("type", participant_type)
            if participant_role:
                data.setdefault("role", participant_role)
            metadata_handle = (manifest_entry.metadata or {}).get("handle")
            if metadata_handle and not data.get("handle"):
                data["handle"] = metadata_handle
            if metadata_handle and not data.get("name"):
                data["name"] = metadata_handle
            elif not data.get("name"):
                data["name"] = manifest_entry.participant_id
            source_id = data.get("source_id")
            if source_id and _normalize_uuid(source_id) == canonical_actor_id:
                data["source_id"] = None
        else:
            if actor_id:
                data["actor_id"] = actor_id
                data.setdefault("id", actor_id)
            elif data.get("id"):
                data["id"] = str(data["id"]).strip()

        resolved.append(data)

    return resolved


def _build_index_payload(
    runtime_root: Path,
    process_slug: str,
    thread_slug: str,
    *,
    candidate_documents: dict[Path, tuple[dict[str, object], str]],
) -> dict[str, object]:
    thread_entry = _thread_entry(runtime_root, process_slug, thread_slug)
    process_id = getattr(thread_entry, "process_id", None) if thread_entry else None
    thread_id = getattr(thread_entry, "thread_id", None) if thread_entry else None

    repo_root = _repo_root(runtime_root)
    generated_at = _isoformat(_iso_now())
    entries: list[dict[str, object]] = []

    for path, (metadata, body) in sorted(candidate_documents.items()):
        slug = path.stem
        message_count = _count_messages(body)
        entry = {
            "conversation_id": metadata.get("conversation_id"),
            "process_id": process_id,
            "thread_id": thread_id,
            "file_path": _relativize(path, repo_root),
            "slug": slug,
            "title": metadata.get("title"),
            "created_at": metadata.get("created_at"),
            "updated_at": metadata.get("updated_at"),
            "message_count": message_count,
            "participants_count": _participants_count(metadata),
            "metadata": {"storage_mode": "filesystem"},
            "hash": _document_hash(_compose_document(metadata, body)),
        }
        entries.append(entry)

    return {
        "index_version": "2.0.0",
        "generated_at": generated_at,
        "entries": entries,
    }


def _conversation_context(function: str, selectors: Mapping[str, str]) -> OperationContext:
    return OperationContext(object_type="conversation", function=function, selectors=selectors)


@dataclass(frozen=True)
class ConversationPlanResult:
    plan: OperationPlan
    payload: object


def plan_create_conversation(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    title: str,
    description: str | None,
    participants: Sequence[Mapping[str, object]],
    slug: str | None = None,
) -> ConversationPlanResult:
    runtime_root = Path(runtime_root).resolve()
    now = _iso_now()
    safe_slug = slug or _slugify(title or "conversation")
    timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
    filename = f"{timestamp}-{safe_slug}"
    conversation_path = _conversation_path(runtime_root, process_slug, thread_slug, filename)

    conversation_id = str(uuid4())
    canonical_participants = _canonicalize_participants(runtime_root, process_slug, thread_slug, participants)
    serialised_participants = _serialise_participants(canonical_participants)
    metadata: dict[str, object] = {
        "conversation_id": conversation_id,
        "description": description or "",
        "updated_at": _isoformat(now),
        "participants": serialised_participants,
    }
    _ensure_created(metadata, now)
    _ensure_title(metadata, title, safe_slug)

    body = f"# {title or 'Conversation'}"
    content = _compose_document(metadata, body)

    existing_docs = _load_existing_documents(runtime_root, process_slug, thread_slug)
    candidate_docs = dict(existing_docs)
    candidate_docs[conversation_path] = (metadata, body)

    index_payload = _build_index_payload(
        runtime_root,
        process_slug,
        thread_slug,
        candidate_documents=candidate_docs,
    )

    ensures = (EnsureInstruction(path=conversation_path.parent),)

    writes = (
        WriteInstruction(
            path=conversation_path,
            content=content,
            policy=OperationWritePolicy.WRITE_ONCE,
            event="created",
            doc_type="conversation-doc",
            timestamp=now,
            metadata={"slug": conversation_path.stem, "conversation_id": conversation_id},
        ),
        WriteInstruction(
            path=_conversation_dir(runtime_root, process_slug, thread_slug) / ".index.json",
            content=json.dumps(index_payload, indent=2) + "\n",
            policy=OperationWritePolicy.MODIFIABLE,
            event="modified",
            doc_type="conversation-index",
            timestamp=now,
            metadata={"entries": len(index_payload["entries"])},
        ),
    )

    selectors = {
        "process_slug": process_slug,
        "thread_slug": thread_slug,
        "conversation_slug": conversation_path.stem,
    }

    plan = OperationPlan(
        context=_conversation_context("create", selectors),
        ensure_dirs=ensures,
        writes=writes,
    )

    summary = ConversationListEntry(
        id=f"{process_slug}/{thread_slug}/{conversation_path.stem}",
        uuid=conversation_id,
        process_slug=process_slug,
        thread_slug=thread_slug,
        slug=conversation_path.stem,
        conversation_id=conversation_id,
        title=metadata.get("title"),
        description=metadata.get("description"),
        created_at=metadata.get("created_at"),
        updated_at=metadata.get("updated_at"),
        participant_count=_participants_count(metadata),
        path=conversation_path,
        index_entry=None,
    )

    return ConversationPlanResult(plan=plan, payload=summary)


def _load_existing_documents(
    runtime_root: Path,
    process_slug: str,
    thread_slug: str,
) -> dict[Path, tuple[dict[str, object], str]]:
    conversations_dir = _conversation_dir(runtime_root, process_slug, thread_slug)
    documents: dict[Path, tuple[dict[str, object], str]] = {}
    if not conversations_dir.exists():
        return documents
    for path in sorted(conversations_dir.glob("*.md")):
        result = _parse_document(path)
        metadata = dict(result.metadata)
        _normalise_metadata_dates(metadata)
        metadata.setdefault("updated_at", metadata.get("created_at"))
        documents[path] = (metadata, result.body)
    return documents


def _prepare_update_payload(
    runtime_root: Path,
    conversation_path: Path,
    metadata: dict[str, object],
    body: str,
    *,
    process_slug: str,
    thread_slug: str,
    function: str,
    event: str,
    policy: OperationWritePolicy,
    now: datetime,
) -> ConversationPlanResult:
    content = _compose_document(metadata, body)

    existing_docs = _load_existing_documents(runtime_root, process_slug, thread_slug)
    candidate_docs = dict(existing_docs)
    candidate_docs[conversation_path] = (metadata, body)

    index_payload = _build_index_payload(
        runtime_root,
        process_slug,
        thread_slug,
        candidate_documents=candidate_docs,
    )

    writes = []
    patches: list[PatchInstruction] = []

    ensures = [EnsureInstruction(path=conversation_path.parent)]
    index_path = _conversation_dir(runtime_root, process_slug, thread_slug) / ".index.json"
    ensures.append(EnsureInstruction(path=index_path.parent))

    if conversation_path.exists():
        original_text = conversation_path.read_text(encoding="utf-8")
        patch_instruction, _ = build_patch_instruction_from_text(
            path=conversation_path,
            original_text=original_text,
            updated_text=content,
            doc_type="conversation-doc",
            timestamp=now,
            policy=policy,
            metadata={"slug": conversation_path.stem, "conversation_id": metadata.get("conversation_id")},
            summary=f"Updated conversation {conversation_path.stem}",
            event=event,
        )
        if patch_instruction is not None:
            patches.append(patch_instruction)
    else:
        writes.append(
            WriteInstruction(
                path=conversation_path,
                content=content,
                policy=policy,
                event=event,
                doc_type="conversation-doc",
                timestamp=now,
                metadata={"slug": conversation_path.stem, "conversation_id": metadata.get("conversation_id")},
            )
        )

    index_content = json.dumps(index_payload, indent=2) + "\n"
    if index_path.exists():
        original_index = index_path.read_text(encoding="utf-8")
        patch_instruction, _ = build_patch_instruction_from_text(
            path=index_path,
            original_text=original_index,
            updated_text=index_content,
            doc_type="conversation-index",
            timestamp=now,
            policy=OperationWritePolicy.MODIFIABLE,
            metadata={"entries": len(index_payload["entries"])},
            summary=f"Updated conversation index for {process_slug}/{thread_slug}",
            event="modified",
        )
        if patch_instruction is not None:
            patches.append(patch_instruction)
    else:
        writes.append(
            WriteInstruction(
                path=index_path,
                content=index_content,
                policy=OperationWritePolicy.MODIFIABLE,
                event="modified",
                doc_type="conversation-index",
                timestamp=now,
                metadata={"entries": len(index_payload["entries"])},
            )
        )

    selectors = {
        "process_slug": process_slug,
        "thread_slug": thread_slug,
        "conversation_slug": conversation_path.stem,
    }

    plan = OperationPlan(
        context=_conversation_context(function, selectors),
        ensure_dirs=tuple(ensures),
        writes=tuple(writes),
        patches=tuple(patches),
    )

    payload = {
        "conversation": f"{process_slug}/{thread_slug}/{conversation_path.stem}",
        "updated_at": metadata.get("updated_at"),
        "participant_count": _participants_count(metadata),
    }

    return ConversationPlanResult(plan=plan, payload=payload)


def plan_append_message(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    conversation_slug: str,
    actor_id: str,
    content: str,
    message_id: str,
    created_at: datetime,
    receiver_id: str | None,
    status: str | None,
    message_type: str | None,
) -> ConversationPlanResult:
    runtime_root = Path(runtime_root).resolve()
    conversation_path = _conversation_path(runtime_root, process_slug, thread_slug, conversation_slug)
    if not conversation_path.exists():
        raise FileNotFoundError(f"Conversation document not found at {conversation_path}")

    result = _parse_document(conversation_path)
    metadata = dict(result.metadata)
    _normalise_metadata_dates(metadata)
    now = _iso_now()
    metadata["updated_at"] = _isoformat(now)

    message_meta = _message_metadata(
        message_id=message_id,
        actor_id=actor_id,
        created_at=created_at,
        receiver_id=receiver_id,
        status=status,
        message_type=message_type,
    )
    block = _build_message_block(message_meta, content)
    body = result.body.rstrip()
    if body:
        body = f"{body}\n\n{block}"
    else:
        body = block

    plan_result = _prepare_update_payload(
        runtime_root,
        conversation_path,
        metadata,
        body,
        process_slug=process_slug,
        thread_slug=thread_slug,
        function="append",
        event="modified",
        policy=OperationWritePolicy.MODIFIABLE,
        now=now,
    )

    payload = ConversationAppendResult(message_id=message_id)
    return ConversationPlanResult(plan=plan_result.plan, payload=payload)


def plan_update_participants(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    conversation_slug: str,
    participants: Sequence[Mapping[str, object]],
) -> ConversationPlanResult:
    runtime_root = Path(runtime_root).resolve()
    conversation_path = _conversation_path(runtime_root, process_slug, thread_slug, conversation_slug)
    if not conversation_path.exists():
        raise FileNotFoundError(f"Conversation document not found at {conversation_path}")

    result = _parse_document(conversation_path)
    metadata = dict(result.metadata)
    _normalise_metadata_dates(metadata)
    now = _iso_now()
    canonical = _canonicalize_participants(runtime_root, process_slug, thread_slug, participants)
    serialised = _serialise_participants(canonical)
    metadata["participants"] = serialised
    metadata["updated_at"] = _isoformat(now)

    plan_result = _prepare_update_payload(
        runtime_root,
        conversation_path,
        metadata,
        result.body,
        process_slug=process_slug,
        thread_slug=thread_slug,
        function="participants",
        event="modified",
        policy=OperationWritePolicy.MODIFIABLE,
        now=now,
    )

    participants_models = [ConversationParticipant.model_validate(participant) for participant in serialised]
    payload = ConversationParticipantsResult(participants=participants_models)
    return ConversationPlanResult(plan=plan_result.plan, payload=payload)


def plan_repair_participants(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    conversation_slug: str,
    participants: Sequence[Mapping[str, object]],
) -> ConversationPlanResult:
    return plan_update_participants(
        runtime_root,
        process_slug=process_slug,
        thread_slug=thread_slug,
        conversation_slug=conversation_slug,
        participants=participants,
    )


def plan_refresh_index(
    runtime_root: Path,
    *,
    targets: Sequence[tuple[str, str]],
) -> ConversationPlanResult:
    runtime_root = Path(runtime_root).resolve()
    now = _iso_now()

    writes: list[WriteInstruction] = []
    patches: list[PatchInstruction] = []
    ensures: list[EnsureInstruction] = []
    threads_payload: list[ConversationIndexRefreshThread] = []

    for process_slug, thread_slug in targets:
        documents = _load_existing_documents(runtime_root, process_slug, thread_slug)
        if not documents:
            continue

        index_payload = _build_index_payload(
            runtime_root,
            process_slug,
            thread_slug,
            candidate_documents=documents,
        )

        index_path = _conversation_dir(runtime_root, process_slug, thread_slug) / ".index.json"
        ensures.append(EnsureInstruction(path=index_path.parent))
        index_content = json.dumps(index_payload, indent=2) + "\n"
        if index_path.exists():
            original_index = index_path.read_text(encoding="utf-8")
            patch_instruction, _ = build_patch_instruction_from_text(
                path=index_path,
                original_text=original_index,
                updated_text=index_content,
                doc_type="conversation-index",
                timestamp=now,
                policy=OperationWritePolicy.MODIFIABLE,
                metadata={"entries": len(index_payload["entries"])},
                summary=f"Refreshed conversation index for {process_slug}/{thread_slug}",
                event="modified",
            )
            if patch_instruction is not None:
                patches.append(patch_instruction)
        else:
            writes.append(
                WriteInstruction(
                    path=index_path,
                    content=index_content,
                    policy=OperationWritePolicy.MODIFIABLE,
                    event="modified",
                    doc_type="conversation-index",
                    timestamp=now,
                    metadata={"entries": len(index_payload["entries"])},
                )
            )
        threads_payload.append(
            ConversationIndexRefreshThread(
                process_slug=process_slug,
                thread_slug=thread_slug,
                path=index_path,
                entry_count=len(index_payload["entries"]),
            )
        )

    selectors: dict[str, str]
    if len(targets) == 1:
        process_slug, thread_slug = targets[0]
        selectors = {"process_slug": process_slug, "thread_slug": thread_slug}
    else:
        selectors = {"scope": "conversation-index-refresh", "targets": str(len(targets))}

    plan = OperationPlan(
        context=_conversation_context("index-refresh", selectors),
        ensure_dirs=tuple(ensures),
        writes=tuple(writes),
        patches=tuple(patches),
    )

    total_entries = sum(thread.entry_count for thread in threads_payload)
    payload = ConversationIndexRefreshResult(count=total_entries, threads=threads_payload)
    return ConversationPlanResult(plan=plan, payload=payload)
