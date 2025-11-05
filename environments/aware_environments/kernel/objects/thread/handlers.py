"""Kernel handlers for thread object functions."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
from typing import Dict, List, Optional

from aware_environment.fs import OperationPlan

from .._shared.frontmatter import load_frontmatter
from .._shared.fs_utils import ensure_iso_timestamp
from .._shared.runtime_models import RuntimeEvent
from .schemas import (
    ThreadEntry,
    ThreadParticipant,
    ThreadParticipantRole,
    ThreadParticipantSession,
    ThreadParticipantSessionState,
    ThreadParticipantStatus,
    ThreadParticipantType,
    ThreadParticipantsManifest,
)
from .._shared.timeline import ensure_datetime
from .fs import ThreadFSAdapter
from .helpers import build_conversation_branch_bundle, build_task_branch_bundle
from .write_plan import (
    ThreadPlanResult,
    plan_branch_write,
    plan_migrate_singleton_branch,
    plan_participants_manifest,
)


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


def list_threads(runtime_root: Path, *, process_slug: Optional[str] = None) -> List[Dict[str, object]]:
    adapter = ThreadFSAdapter(runtime_root)
    entries = adapter.list_threads(process_slug=process_slug)
    return [_thread_entry_to_dict(entry) for entry in entries]


def thread_status(runtime_root: Path, identifier: str) -> Dict[str, object]:
    adapter = ThreadFSAdapter(runtime_root)
    entry = adapter.get_thread(identifier)
    if entry is None:
        raise ValueError(f"Thread '{identifier}' not found.")
    payload = _thread_entry_to_dict(entry)
    payload["branches"] = adapter.list_branches(entry)
    return payload


def thread_activity(
    runtime_root: Path,
    identifier: str,
    *,
    since: Optional[str] = None,
) -> List[Dict[str, object]]:
    adapter = ThreadFSAdapter(runtime_root)
    entry = adapter.get_thread(identifier)
    if entry is None:
        raise ValueError(f"Thread '{identifier}' not found.")
    since_dt: Optional[datetime] = ensure_datetime(since) if since else None
    events = adapter.collect_activity(entry, since=since_dt)
    return [_runtime_event_to_dict(evt) for evt in events]


def thread_branches(runtime_root: Path, identifier: str) -> List[Dict[str, object]]:
    adapter = ThreadFSAdapter(runtime_root)
    entry = adapter.get_thread(identifier)
    if entry is None:
        raise ValueError(f"Thread '{identifier}' not found.")
    return adapter.list_branches(entry)


def thread_conversations(
    runtime_root: Path,
    identifier: str,
    *,
    since: Optional[str] = None,
) -> List[Dict[str, object]]:
    adapter = ThreadFSAdapter(runtime_root)
    entry = adapter.get_thread(identifier)
    if entry is None:
        raise ValueError(f"Thread '{identifier}' not found.")
    since_dt: Optional[datetime] = ensure_datetime(since) if since else None
    return adapter.list_conversations(entry, since=since_dt)


def thread_document(
    runtime_root: Path,
    identifier: str,
    *,
    path: str,
) -> Path:
    adapter = ThreadFSAdapter(runtime_root)
    entry = adapter.get_thread(identifier)
    if entry is None:
        raise ValueError(f"Thread '{identifier}' not found.")
    document_path = adapter.load_document(entry, path)
    if not document_path.exists():
        raise ValueError(f"Document '{path}' not found for thread '{identifier}'.")
    return document_path


def _resolve_runtime_root(runtime_root: Optional[str | Path]) -> Path:
    if runtime_root is None:
        base = Path("docs") / "runtime" / "process"
    else:
        base = Path(runtime_root)
    return base.expanduser().resolve()


def _resolve_identifier(process: Optional[str], thread: Optional[str]) -> str:
    process_slug = process or "main"
    thread_slug = thread or "main"
    return f"{process_slug}/{thread_slug}"


def _get_thread_adapter_entry(
    runtime_root: Optional[str | Path],
    process: Optional[str],
    thread: Optional[str],
) -> tuple[ThreadFSAdapter, ThreadEntry]:
    root = _resolve_runtime_root(runtime_root)
    adapter = ThreadFSAdapter(root)
    identifier = _resolve_identifier(process, thread)
    entry = adapter.get_thread(identifier)
    if entry is None:
        raise ValueError(f"Thread '{identifier}' not found.")
    return adapter, entry


def _ensure_mapping(value: object, name: str) -> Dict[str, object]:
    if value is None:
        raise ValueError(f"{name} is required.")
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError(f"{name} must be valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{name} must be a JSON object.")
        return parsed
    raise ValueError(f"{name} must be a mapping.")


def _coerce_role(value: object) -> ThreadParticipantRole | None:
    if value is None:
        return None
    if isinstance(value, ThreadParticipantRole):
        return value
    try:
        return ThreadParticipantRole(str(value).lower())
    except ValueError as exc:  # pragma: no cover - defensive
        choices = ", ".join(sorted(role.value for role in ThreadParticipantRole))
        raise ValueError(f"Unknown participant role '{value}'. Expected one of: {choices}.") from exc


def _coerce_status(value: object) -> ThreadParticipantStatus | None:
    if value is None:
        return None
    if isinstance(value, ThreadParticipantStatus):
        return value
    try:
        return ThreadParticipantStatus(str(value).lower())
    except ValueError as exc:  # pragma: no cover - defensive
        choices = ", ".join(sorted(status.value for status in ThreadParticipantStatus))
        raise ValueError(f"Unknown participant status '{value}'. Expected one of: {choices}.") from exc


def _coerce_session_state(value: object) -> ThreadParticipantSessionState | None:
    if value is None:
        return None
    if isinstance(value, ThreadParticipantSessionState):
        return value
    try:
        return ThreadParticipantSessionState(str(value).lower())
    except ValueError as exc:  # pragma: no cover - defensive
        choices = ", ".join(sorted(state.value for state in ThreadParticipantSessionState))
        raise ValueError(f"Unknown session state '{value}'. Expected one of: {choices}.") from exc


def _coerce_last_seen(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return ensure_datetime(value)
    raise ValueError("last_seen must be an ISO8601 string or datetime.")


def _participant_to_dict(part: ThreadParticipant) -> Dict[str, object]:
    payload = part.model_dump_json_ready()
    payload["last_seen"] = ensure_iso_timestamp(part.last_seen)
    session = payload.get("session")
    if isinstance(session, dict):
        if part.session:
            session["state"] = part.session.state.value
            session["updated_at"] = ensure_iso_timestamp(getattr(part.session, "updated_at", None))
        else:
            session["state"] = None
            session["updated_at"] = None
    return payload


def thread_status_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
) -> Dict[str, object]:
    root = _resolve_runtime_root(runtime_root)
    identifier = _resolve_identifier(process, thread)
    return thread_status(root, identifier)


def thread_list_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
) -> List[Dict[str, object]]:
    root = _resolve_runtime_root(runtime_root)
    adapter = ThreadFSAdapter(root)
    entries = adapter.list_threads(process_slug=process)
    return [_thread_entry_to_dict(entry) for entry in entries]


def thread_branches_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
) -> List[Dict[str, object]]:
    root = _resolve_runtime_root(runtime_root)
    identifier = _resolve_identifier(process, thread)
    return thread_branches(root, identifier)


def thread_pane_manifest_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    pane: str,
    branch_id: Optional[str] = None,
) -> Dict[str, object]:
    root = _resolve_runtime_root(runtime_root)
    identifier = _resolve_identifier(process, thread)
    adapter = ThreadFSAdapter(root)
    entry = adapter.get_thread(identifier)
    if entry is None:
        raise ValueError(f"Thread '{identifier}' not found.")
    data = adapter.load_branch_manifest(entry, pane, branch_id=branch_id)
    if not data.get("branch"):
        raise FileNotFoundError(f"Branch manifest for pane '{pane}' (branch '{branch_id or pane}') not found.")
    return data


def thread_backlog_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    since: Optional[str] = None,
) -> List[Dict[str, object]]:
    root = _resolve_runtime_root(runtime_root)
    identifier = _resolve_identifier(process, thread)
    adapter = ThreadFSAdapter(root)
    entry = adapter.get_thread(identifier)
    if entry is None:
        raise ValueError(f"Thread '{identifier}' not found.")
    since_dt: Optional[datetime] = ensure_datetime(since) if since else None
    events = adapter.collect_activity(entry, since=since_dt)
    backlog_events = [evt for evt in events if evt.event_type == "backlog"]
    return [_runtime_event_to_dict(evt) for evt in backlog_events]


def thread_activity_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    since: Optional[str] = None,
) -> Dict[str, object]:
    root = _resolve_runtime_root(runtime_root)
    identifier = _resolve_identifier(process, thread)
    events = thread_activity(root, identifier, since=since)
    return {"events": events}


def thread_conversations_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    since: Optional[str] = None,
) -> Dict[str, object]:
    root = _resolve_runtime_root(runtime_root)
    identifier = _resolve_identifier(process, thread)
    conversations = thread_conversations(root, identifier, since=since)
    return {"conversations": conversations}


def thread_document_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    path: str,
    format: str = "json",
) -> Dict[str, object]:
    root = _resolve_runtime_root(runtime_root)
    identifier = _resolve_identifier(process, thread)
    document_path = thread_document(root, identifier, path=path)
    fmt = (format or "json").lower()
    if fmt not in {"json", "markdown"}:
        raise ValueError("format must be 'json' or 'markdown'.")

    if fmt == "markdown":
        content = document_path.read_text(encoding="utf-8")
        return {
            "format": "markdown",
            "markdown": content,
            "path": str(document_path),
        }

    frontmatter = load_frontmatter(document_path)
    metadata = _sanitize_metadata(frontmatter.metadata or {})
    return {
        "format": "json",
        "metadata": metadata,
        "body": frontmatter.body,
        "path": str(document_path),
    }


def thread_participants_list_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    participant_id: Optional[str] = None,
    json: bool = False,
) -> Dict[str, object] | List[Dict[str, object]]:
    root = _resolve_runtime_root(runtime_root)
    identifier = _resolve_identifier(process, thread)
    adapter = ThreadFSAdapter(root)
    entry = adapter.get_thread(identifier)
    if entry is None:
        raise ValueError(f"Thread '{identifier}' not found.")
    manifest = adapter.load_participants_manifest(entry)
    if json:
        payload = manifest.model_dump_json_ready()
        return payload  # raw dump for tooling parity

    filtered: List[ThreadParticipant] = []
    desired_type: Optional[ThreadParticipantType] = None
    desired_status: Optional[ThreadParticipantStatus] = None
    if type:
        try:
            desired_type = ThreadParticipantType(type.lower())
        except ValueError as exc:
            choices = ", ".join(sorted(tp.value for tp in ThreadParticipantType))
            raise ValueError(f"Unknown participant type '{type}'. Expected one of: {choices}.") from exc
    if status:
        try:
            desired_status = ThreadParticipantStatus(status.lower())
        except ValueError as exc:
            choices = ", ".join(sorted(st.value for st in ThreadParticipantStatus))
            raise ValueError(f"Unknown participant status '{status}'. Expected one of: {choices}.") from exc

    for participant in manifest.participants:
        if desired_type and participant.type is not desired_type:
            continue
        if desired_status and participant.status is not desired_status:
            continue
        if participant_id and participant.participant_id != participant_id:
            continue
        filtered.append(participant)

    return [_participant_to_dict(part) for part in filtered]


def _branch_write(
    function_name: str,
    *,
    runtime_root: Optional[str | Path],
    process: Optional[str],
    thread: Optional[str],
    pane: str,
    branch: Dict[str, object] | str | None,
    pane_manifest: Dict[str, object] | str | None,
    manifest_version: int = 1,
    task_binding: Dict[str, object] | str | None = None,
) -> ThreadPlanResult:
    branch_payload = _ensure_mapping(branch, "branch")
    pane_manifest_payload = _ensure_mapping(pane_manifest, "pane_manifest")
    binding_payload = None
    if task_binding is not None:
        binding_payload = _ensure_mapping(task_binding, "task_binding")

    adapter, entry = _get_thread_adapter_entry(runtime_root, process, thread)
    plan_result = plan_branch_write(
        entry,
        function_name=function_name,
        pane_kind=pane,
        branch=branch_payload,
        pane_manifest=pane_manifest_payload,
        manifest_version=manifest_version,
        task_binding=binding_payload,
    )
    return plan_result


def thread_branch_set_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    pane: str,
    branch: Dict[str, object] | str | None = None,
    pane_manifest: Dict[str, object] | str | None = None,
    manifest_version: int = 1,
    task_binding: Dict[str, object] | str | None = None,
    task: Optional[str] = None,
    projects_root: Optional[str] = None,
) -> ThreadPlanResult:
    if task:
        _, entry = _get_thread_adapter_entry(runtime_root, process, thread)
        bundle = build_task_branch_bundle(
            entry,
            task_identifier=task,
            projects_root=projects_root,
        )
        branch = bundle.branch.model_dump(mode="json")
        pane_manifest = bundle.pane_manifest.model_dump(mode="json")
        task_binding = bundle.task_binding.model_dump(mode="json")
        manifest_version = bundle.manifest_version

    return _branch_write(
        "branch-set",
        runtime_root=runtime_root,
        process=process,
        thread=thread,
        pane=pane,
        branch=branch,
        pane_manifest=pane_manifest,
        manifest_version=manifest_version,
        task_binding=task_binding,
    )


def thread_branch_migrate_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    pane: str,
    branch: Dict[str, object] | str | None = None,
    pane_manifest: Dict[str, object] | str | None = None,
    manifest_version: int = 1,
    task_binding: Dict[str, object] | str | None = None,
    task: Optional[str] = None,
    conversation: Optional[str] = None,
    projects_root: Optional[str] = None,
    migrate_singleton: bool = False,
) -> ThreadPlanResult:
    runtime_root_path = _resolve_runtime_root(runtime_root)
    branch_payload = branch
    pane_manifest_payload = pane_manifest
    binding_payload = task_binding

    if conversation:
        _, entry = _get_thread_adapter_entry(runtime_root, process, thread)
        branch_payload, pane_manifest_payload = build_conversation_branch_bundle(
            runtime_root_path,
            entry,
            conversation_identifier=conversation,
        )
    elif task:
        _, entry = _get_thread_adapter_entry(runtime_root, process, thread)
        bundle = build_task_branch_bundle(
            entry,
            task_identifier=task,
            projects_root=projects_root,
        )
        branch_payload = bundle.branch.model_dump(mode="json")
        pane_manifest_payload = bundle.pane_manifest.model_dump(mode="json")
        binding_payload = bundle.task_binding.model_dump(mode="json")
        manifest_version = bundle.manifest_version
    elif migrate_singleton:
        _, entry = _get_thread_adapter_entry(runtime_root, process, thread)
        return plan_migrate_singleton_branch(entry, pane_kind=pane)

    return _branch_write(
        "branch-migrate",
        runtime_root=runtime_root,
        process=process,
        thread=thread,
        pane=pane,
        branch=branch_payload,
        pane_manifest=pane_manifest_payload,
        manifest_version=manifest_version,
        task_binding=binding_payload,
    )


def thread_branch_refresh_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    pane: str,
    branch_id: Optional[str] = None,
) -> ThreadPlanResult:
    adapter, entry = _get_thread_adapter_entry(runtime_root, process, thread)
    data = adapter.load_branch_manifest(entry, pane, branch_id=branch_id)
    branch_payload = data.get("branch")
    if not branch_payload:
        target = branch_id or pane
        raise ValueError(f"Branch '{target}' not found for pane '{pane}'.")
    manifest_payload = data.get("pane_manifest") or {}
    manifest_version = manifest_payload.get("manifest_version", 1)
    return plan_branch_write(
        entry,
        function_name="branch-refresh",
        pane_kind=pane,
        branch=dict(branch_payload),
        pane_manifest=dict(manifest_payload),
        manifest_version=manifest_version,
    )


def thread_participants_bind_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    participant: Dict[str, object] | str | None,
    force: bool = False,
) -> ThreadPlanResult:
    participant_payload = _ensure_mapping(participant, "participant")
    participant_model = ThreadParticipant.model_validate(participant_payload)

    adapter, entry = _get_thread_adapter_entry(runtime_root, process, thread)
    manifest = adapter.load_participants_manifest(entry)

    participants: List[ThreadParticipant] = []
    replaced = False
    for existing in manifest.participants:
        if existing.participant_id == participant_model.participant_id:
            if not force:
                raise ValueError(
                    f"Participant '{participant_model.participant_id}' already exists. Use force=True to replace."
                )
            participants.append(participant_model)
            replaced = True
        else:
            participants.append(existing)

    if not replaced:
        participants.append(participant_model)

    manifest.participants = participants
    plan_result = plan_participants_manifest(entry, function_name="participants-bind", manifest=manifest)

    payload = dict(plan_result.payload)
    payload.update(
        {
            "thread_id": manifest.thread_id,
            "participant": _participant_to_dict(participant_model),
            "replaced": replaced,
        }
    )

    return ThreadPlanResult(plans=plan_result.plans, payload=payload)


def thread_participants_update_handler(
    runtime_root: Optional[str | Path] = None,
    *,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    participant_id: str,
    updates: Dict[str, object] | str | None,
) -> ThreadPlanResult:
    updates_payload = _ensure_mapping(updates, "updates")

    adapter, entry = _get_thread_adapter_entry(runtime_root, process, thread)
    manifest = adapter.load_participants_manifest(entry)

    participants: List[ThreadParticipant] = []
    updated_participant: ThreadParticipant | None = None

    for existing in manifest.participants:
        if existing.participant_id != participant_id:
            participants.append(existing)
            continue

        update_kwargs: Dict[str, object] = {}
        if "role" in updates_payload:
            role_value = _coerce_role(updates_payload.get("role"))
            if role_value is not None:
                update_kwargs["role"] = role_value
        if "status" in updates_payload:
            status_value = _coerce_status(updates_payload.get("status"))
            if status_value is not None:
                update_kwargs["status"] = status_value
        if "last_seen" in updates_payload:
            update_kwargs["last_seen"] = _coerce_last_seen(updates_payload.get("last_seen"))
        if "metadata" in updates_payload:
            metadata_value = _ensure_mapping(updates_payload.get("metadata"), "metadata")
            update_kwargs["metadata"] = metadata_value

        session_updates_raw = updates_payload.get("session")
        if session_updates_raw is not None:
            session_updates_map = _ensure_mapping(session_updates_raw, "session")
            session_update_kwargs: Dict[str, object] = {}
            if "session_id" in session_updates_map:
                session_update_kwargs["session_id"] = session_updates_map["session_id"]
            if "transport" in session_updates_map:
                session_update_kwargs["transport"] = session_updates_map["transport"]
            if "daemon_pid" in session_updates_map:
                session_update_kwargs["daemon_pid"] = session_updates_map["daemon_pid"]
            if "state" in session_updates_map:
                state_value = _coerce_session_state(session_updates_map.get("state"))
                if state_value is not None:
                    session_update_kwargs["state"] = state_value
            session_model = existing.session.model_copy(update=session_update_kwargs)
            update_kwargs["session"] = session_model

        if not update_kwargs:
            raise ValueError("No updates provided. Specify at least one field to update.")

        updated_participant = existing.model_copy(update=update_kwargs)
        participants.append(updated_participant)

    if updated_participant is None:
        raise ValueError(f"Participant '{participant_id}' not found.")

    manifest.participants = participants
    plan_result = plan_participants_manifest(entry, function_name="participants-update", manifest=manifest)

    payload = dict(plan_result.payload)
    payload.update(
        {
            "thread_id": manifest.thread_id,
            "participant": _participant_to_dict(updated_participant),
        }
    )

    return ThreadPlanResult(plans=plan_result.plans, payload=payload)


__all__ = [
    "list_threads",
    "thread_status",
    "thread_activity",
    "thread_branches",
    "thread_conversations",
    "thread_document",
    "thread_list_handler",
    "thread_status_handler",
    "thread_branches_handler",
    "thread_branch_set_handler",
    "thread_branch_migrate_handler",
    "thread_branch_refresh_handler",
    "thread_pane_manifest_handler",
    "thread_backlog_handler",
    "thread_activity_handler",
    "thread_conversations_handler",
    "thread_document_handler",
    "thread_participants_bind_handler",
    "thread_participants_update_handler",
    "thread_participants_list_handler",
]
