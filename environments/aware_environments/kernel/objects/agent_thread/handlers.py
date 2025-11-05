"""Kernel handlers for agent thread lifecycle operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Mapping
from uuid import UUID, uuid4

from ..agent.adapter import create_process, create_thread
from ..agent.helpers import _aware_home
from .._shared.fs_utils import _safe_load_json
from .session_ops import _agent_thread_metadata_path, _iso_now, session_update
from .schemas import (
    AgentThreadDocument,
    AgentProcessThreadMetadata,
    AgentProcessMetadata,
    AgentMetadata,
    AgentThreadLoginResult,
    AgentThreadLoginSession,
)
from ..thread.schemas import (
    ThreadParticipant,
    ThreadParticipantIdentityAgent,
    ThreadParticipantRole,
    ThreadParticipantSession,
    ThreadParticipantSessionState,
    ThreadParticipantStatus,
    ThreadParticipantType,
    ThreadParticipantsManifest,
)
from ..thread.fs import ThreadFSAdapter
from ..terminal import handlers as terminal_handlers  # local import to avoid circular dependency
from ..terminal.descriptors import descriptor_path as terminal_descriptor_path, load_descriptor
from ..terminal.models import TerminalDescriptorModel
from .write_plan import SessionUpdatePlan, plan_session_update
from aware_environments.kernel._shared.receipts import receipt_to_dict, receipt_to_journal_entry
from aware_environment.fs import apply_plan


def _thread_directory(identities_root: Path, agent: str, process: str, thread: str) -> Path:
    return Path(identities_root) / "agents" / agent / "runtime" / "process" / process / "threads" / thread


def _load_thread_document(path: Path) -> AgentThreadDocument:
    data = _safe_load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid agent thread document at {path}")
    return AgentThreadDocument.model_validate(data)


def _to_uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"{field} is not a valid UUID: {value}") from exc


def _load_agent_identity(
    identities_root: Path, agent: str, process: str, thread: str
) -> Tuple[ThreadParticipantIdentityAgent, str]:
    thread_dir = _thread_directory(identities_root, agent, process, thread)
    thread_json = thread_dir / "agent_process_thread.json"
    if not thread_json.exists():
        raise ValueError(f"Agent process thread metadata not found at {thread_json}")
    raw_thread = _safe_load_json(thread_json)
    if not isinstance(raw_thread, dict):
        raise ValueError(f"Invalid agent thread metadata at {thread_json}")
    thread_data = AgentProcessThreadMetadata.model_validate(raw_thread)

    apt_id = thread_data.id
    agent_process_id = thread_data.agent_process_id
    actor_id = thread_data.actor_id

    process_json = thread_dir.parent.parent / "agent_process.json"
    raw_process = _safe_load_json(process_json)
    if not isinstance(raw_process, dict):
        raise ValueError(f"Agent process metadata not found at {process_json}")
    process_data = AgentProcessMetadata.model_validate(raw_process)
    agent_id = process_data.agent_id

    agent_json = Path(identities_root) / "agents" / agent / "agent.json"
    raw_agent = _safe_load_json(agent_json)
    if not isinstance(raw_agent, dict):
        raise ValueError(f"Agent metadata not found at {agent_json}")
    agent_data = AgentMetadata.model_validate(raw_agent)
    identity_id = agent_data.identity_id or agent_data.id
    if identity_id is None:
        raise ValueError("agent.json is missing identity identifiers.")

    slug = f"{agent}/{process}/{thread}"
    identity = ThreadParticipantIdentityAgent(
        agent_process_thread_id=_to_uuid(apt_id, "agent_process_thread_id"),
        agent_process_id=_to_uuid(agent_process_id, "agent_process_id"),
        agent_id=_to_uuid(agent_id, "agent_id"),
        identity_id=_to_uuid(identity_id, "identity_id"),
        actor_id=_to_uuid(actor_id, "actor_id"),
        slug=slug,
    )
    return identity, str(identity.agent_process_thread_id)


def _ensure_agent_participant(
    *,
    adapter: ThreadFSAdapter,
    entry,
    manifest: ThreadParticipantsManifest,
    identities_root: Path,
    agent: str,
    process: str,
    thread: str,
    participant_id: str,
) -> ThreadParticipant:
    for participant in manifest.participants:
        if participant.participant_id == participant_id:
            return participant

    identity, default_participant_id = _load_agent_identity(identities_root, agent, process, thread)
    participant = ThreadParticipant(
        participant_id=participant_id or default_participant_id,
        type=ThreadParticipantType.AGENT,
        role=ThreadParticipantRole.EXECUTOR,
        status=ThreadParticipantStatus.PENDING,
        identity=identity,
        session=ThreadParticipantSession(),
        metadata={},
    )
    manifest.participants.append(participant)
    adapter.write_participants_manifest(entry, manifest)
    return participant


def _ensure_runtime_thread_scaffold(
    runtime_root: Path,
    *,
    process_slug: str,
    thread_slug: str,
    thread_doc: AgentThreadDocument,
) -> None:
    runtime_root = Path(runtime_root).resolve()
    process_dir = runtime_root / process_slug
    thread_dir = process_dir / "threads" / thread_slug
    thread_dir.mkdir(parents=True, exist_ok=True)

    thread_json = thread_dir / "thread.json"
    if thread_json.exists():
        return

    created_at = thread_doc.created_at or _iso_now()
    updated_at = thread_doc.updated_at or created_at
    payload = {
        "id": thread_doc.id or str(uuid4()),
        "process_id": thread_doc.agent_process_id,
        "parent_id": None,
        "overview_content_id": None,
        "backlog_chain_id": None,
        "title": thread_doc.name or thread_slug,
        "description": thread_doc.description,
        "is_main": bool(thread_doc.is_main if thread_doc.is_main is not None else thread_slug == "main"),
        "created_at": created_at,
        "updated_at": updated_at,
        "desktop_item_thread_list": [],
        "thread_change_list": [],
        "thread_change_object_instance_graph_change_list": [],
        "thread_object_instance_graph_branch_list": [],
        "thread_task_list": [],
    }
    thread_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _normalize_metadata_strings(metadata: Dict[str, Any]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, str):
            normalized[key] = value
        elif isinstance(value, (int, float, bool)):
            normalized[key] = str(value)
        else:
            try:
                normalized[key] = json.dumps(value)
            except TypeError:
                normalized[key] = str(value)
    return normalized


def signup(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    display_name: Optional[str] = None,
    is_main: bool = False,
    status: str = "running",
    execution_mode: str = "native",
    description: Optional[str] = None,
    force: bool = False,
    runtime_root: Path | str | None = None,
    aware_root: Path | str | None = None,
    provider: Optional[str] = None,
    with_terminal: Optional[str] = None,
    allow_missing_session: bool = False,
    terminal_shell: Optional[str] = None,
) -> Dict[str, Any]:
    identities_root = Path(identities_root).resolve()

    process_result = create_process(
        identities_root,
        agent_slug=agent,
        process_slug=process,
        display_name=display_name,
        force=force,
    )
    thread_dir = identities_root / "agents" / agent / "runtime" / "process" / process / "threads" / thread
    thread_json = thread_dir / "agent_process_thread.json"

    thread_status = "created"
    thread_payload: Dict[str, Any] = {}
    try:
        thread_result = create_thread(
            identities_root,
            agent_slug=agent,
            process_slug=process,
            thread_slug=thread,
            is_main=is_main,
            status=status,
            execution_mode=execution_mode,
            description=description,
        )
        thread_payload = thread_result.payload
        thread_path = thread_result.thread_path
    except FileExistsError:
        thread_status = "exists"
        thread_path = thread_json
        existing_payload = _safe_load_json(thread_json)
        if isinstance(existing_payload, dict):
            thread_payload = dict(existing_payload)

    thread_response: Dict[str, Any] = {
        "slug": thread,
        "status": thread_status,
        "path": str(thread_dir.relative_to(identities_root)) if thread_dir.exists() else None,
    }
    if thread_payload.get("id"):
        thread_response["id"] = thread_payload.get("id")

    terminal_payload: Optional[Dict[str, Any]] = None
    terminal_id = with_terminal
    provider_slug = provider
    thread_metadata = {}
    if isinstance(thread_payload, dict):
        metadata_value = thread_payload.get("metadata")
        if isinstance(metadata_value, dict):
            thread_metadata = dict(metadata_value)

    if terminal_id or provider_slug:
        if provider_slug is None:
            candidate = thread_metadata.get("terminal_provider")
            if isinstance(candidate, str) and candidate:
                provider_slug = candidate
        if provider_slug is None:
            raise ValueError("Provider slug is required when ensuring terminal binding.")

        if not terminal_id:
            candidate_terminal = thread_metadata.get("terminal_id")
            if isinstance(candidate_terminal, str) and candidate_terminal:
                terminal_id = candidate_terminal
            terminal_id = terminal_id or "term-main"

        if isinstance(runtime_root, Path):
            runtime_root_path = runtime_root.expanduser().resolve()
        elif runtime_root:
            runtime_root_path = Path(runtime_root).expanduser().resolve()
        else:
            runtime_root_path = (identities_root.parent / "runtime" / "process").resolve()
        runtime_root_path.mkdir(parents=True, exist_ok=True)

        if isinstance(aware_root, Path):
            aware_root_path = aware_root.expanduser().resolve()
        elif aware_root:
            aware_root_path = Path(aware_root).expanduser().resolve()
        else:
            aware_root_path = _aware_home()
        aware_root_path.mkdir(parents=True, exist_ok=True)

        terminal_payload = login(
            identities_root,
            runtime_root_path,
            aware_root_path,
            agent=agent,
            process=process,
            thread=thread,
            provider=provider_slug,
            terminal_id=terminal_id,
            ensure_terminal=True,
            allow_missing_session=allow_missing_session,
        )

    payload: Dict[str, Any] = {
        "status": thread_status,
        "process": {
            "slug": process,
            "status": process_result.status,
            "path": str(process_result.process_path.parent.relative_to(identities_root)),
        },
        "thread": thread_response,
    }
    if terminal_payload is not None:
        payload["terminal"] = terminal_payload
    return payload


def _session_id_from_payload(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    session_id = (
        payload.get("session_id") or payload.get("data", {}).get("session_id")
        if isinstance(payload.get("data"), dict)
        else None
    )
    if isinstance(session_id, str):
        return session_id
    return None


def _is_uuid_like(value: Optional[str]) -> bool:
    if not value or not isinstance(value, str):
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def login(
    identities_root: Path,
    runtime_root: Path,
    aware_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    provider: str,
    terminal_id: Optional[str] = None,
    ensure_terminal: bool = True,
    allow_missing_session: bool = False,
    skip_resolve: bool = False,
    resume: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if skip_resolve and not allow_missing_session:
        raise ValueError("--allow-missing-session is required when skip_resolve is enabled.")

    if not provider:
        raise ValueError("Provider slug is required for login.")

    identities_root = Path(identities_root).resolve()
    runtime_root = Path(runtime_root).resolve()
    aware_root = Path(aware_root).resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    aware_root.mkdir(parents=True, exist_ok=True)

    thread_doc_path = _agent_thread_metadata_path(identities_root, agent=agent, process=process, thread=thread)
    if not thread_doc_path.exists():
        raise ValueError(f"Agent thread metadata missing at {thread_doc_path}")
    thread_doc = _load_thread_document(thread_doc_path)

    apt_id = thread_doc.id
    if not apt_id:
        raise ValueError("Agent thread metadata missing 'id'.")

    metadata_block = dict(thread_doc.metadata or {})
    provider_slug = provider or metadata_block.get("terminal_provider")
    if not provider_slug:
        raise ValueError("Provider slug could not be determined for login.")

    terminal_identifier = terminal_id or metadata_block.get("terminal_id")
    if ensure_terminal and terminal_identifier is None:
        terminal_identifier = "term-main"

    thread_identifier = f"{process}/{thread}"

    adapter = ThreadFSAdapter(runtime_root)
    entry = adapter.get_thread(thread_identifier)
    if entry is None:
        _ensure_runtime_thread_scaffold(
            runtime_root,
            process_slug=process,
            thread_slug=thread,
            thread_doc=thread_doc,
        )
        adapter = ThreadFSAdapter(runtime_root)
        entry = adapter.get_thread(thread_identifier)
    if entry is None:
        raise ValueError(f"Runtime thread scaffold missing for '{thread_identifier}'.")

    manifest = adapter.load_participants_manifest(entry)
    participant = _ensure_agent_participant(
        adapter=adapter,
        entry=entry,
        manifest=manifest,
        identities_root=identities_root,
        agent=agent,
        process=process,
        thread=thread,
        participant_id=apt_id,
    )

    metadata_updates = dict(participant.metadata or {})
    if metadata:
        metadata_updates.update(metadata)

    operation_receipts: List[Dict[str, Any]] = []
    operation_journal: List[Dict[str, Any]] = []

    descriptor_path: Optional[Path] = None
    descriptor_model: Optional[TerminalDescriptorModel] = None
    if terminal_identifier is not None:
        descriptor_path = terminal_descriptor_path(
            aware_root, entry.thread_id or thread_identifier, terminal_identifier
        )
        descriptor_model = load_descriptor(descriptor_path)

    if ensure_terminal and descriptor_model is None:
        create_result = terminal_handlers.create_terminal(
            runtime_root,
            aware_root,
            thread_identifier=entry.thread_id or thread_identifier,
            terminal_id=terminal_identifier,
        )
        if hasattr(create_result, "plans"):
            for plan in getattr(create_result, "plans", ()):  # apply descriptor/pane writes
                receipt = apply_plan(plan)
                receipt_dict = receipt_to_dict(receipt)
                operation_receipts.append(receipt_dict)
                operation_journal.append(receipt_to_journal_entry(receipt_dict))
            payload_map = getattr(create_result, "payload", {}) or {}
        else:
            payload_map = create_result or {}

        descriptor_path_value = payload_map.get("descriptor_path", descriptor_path or "")
        descriptor_path = Path(descriptor_path_value) if descriptor_path_value else None
        descriptor_payload = payload_map.get("terminal")
        if descriptor_payload is not None:
            descriptor_model = TerminalDescriptorModel.model_validate(descriptor_payload)
        elif descriptor_path:
            descriptor_model = load_descriptor(descriptor_path)
        if descriptor_model is None:
            raise ValueError("Failed to create terminal descriptor during login.")

    if not ensure_terminal and descriptor_model is None:
        raise ValueError("Terminal descriptor not found; enable auto-ensure or supply --terminal-id.")

    if descriptor_model is not None and not terminal_identifier:
        terminal_identifier = descriptor_model.id

    session_payload: Dict[str, Any] = {}
    expected_session_id: Optional[str] = None
    if not skip_resolve:
        resolve_payload = terminal_handlers.session_resolve(
            runtime_root,
            aware_root,
            identities_root,
            thread_identifier=entry.thread_id or thread_identifier,
            provider=provider_slug,
            terminal_id=terminal_identifier,
            apt_id=apt_id,
        )
        session_payload = resolve_payload
        if resolve_payload.get("success"):
            expected_session_id = _session_id_from_payload(resolve_payload.get("data"))
            if expected_session_id and not _is_uuid_like(expected_session_id):
                if allow_missing_session:
                    expected_session_id = None
                else:
                    raise ValueError("Session resolve returned a non-UUID session id; launch the provider and retry.")
        else:
            if allow_missing_session:
                expected_session_id = None
            else:
                message = resolve_payload.get("message", "session resolve failed")
                raise ValueError(f"Session resolve failed: {message}")

    bind_result = terminal_handlers.bind_provider(
        runtime_root,
        aware_root,
        identities_root,
        thread_identifier=entry.thread_id or thread_identifier,
        terminal_id=terminal_identifier or (descriptor_model.id if descriptor_model else None),
        apt_id=participant.participant_id,
        provider=provider_slug,
        resume=resume or bool(expected_session_id),
        metadata=_normalize_metadata_strings(metadata_updates),
    )

    if hasattr(bind_result, "plans"):
        for plan in getattr(bind_result, "plans", ()):  # apply descriptor/participants updates
            receipt = apply_plan(plan)
            receipt_dict = receipt_to_dict(receipt)
            operation_receipts.append(receipt_dict)
            operation_journal.append(receipt_to_journal_entry(receipt_dict))
        bind_payload = getattr(bind_result, "payload", {}) or {}
    else:
        bind_payload = bind_result or {}

    bind_receipts = bind_payload.get("receipts")
    if isinstance(bind_receipts, list):
        for receipt in bind_receipts:
            if isinstance(receipt, Mapping):
                receipt_dict = dict(receipt)
                operation_receipts.append(receipt_dict)
                operation_journal.append(receipt_to_journal_entry(receipt_dict))

    bound_session_id = bind_payload.get("session_id")
    if not allow_missing_session and expected_session_id and bound_session_id != expected_session_id:
        raise ValueError("Provider session id changed during bind; ensure the correct session is active and retry.")

    if not allow_missing_session:
        if not bound_session_id:
            raise ValueError("Provider did not return a session id during bind.")

    canonical_session_id = bound_session_id if bound_session_id is not None else None

    update_payload = session_update(
        identities_root,
        agent=agent,
        process=process,
        thread=thread,
        session_id=canonical_session_id,
        provider=provider_slug,
        terminal_id=terminal_identifier,
    )
    if isinstance(update_payload, SessionUpdatePlan):
        receipt = apply_plan(update_payload.plan)
        receipt_dict = receipt_to_dict(receipt)
        operation_receipts.append(receipt_dict)
        operation_journal.append(receipt_to_journal_entry(receipt_dict))
    elif isinstance(update_payload, Mapping):
        receipts_field = update_payload.get("receipts")
        if isinstance(receipts_field, list):
            for entry in receipts_field:
                if isinstance(entry, Mapping):
                    receipt_dict = dict(entry)
                    operation_receipts.append(receipt_dict)
                    operation_journal.append(receipt_to_journal_entry(receipt_dict))
        journal_field = update_payload.get("journal")
        if isinstance(journal_field, list):
            for entry in journal_field:
                if isinstance(entry, Mapping):
                    operation_journal.append(dict(entry))

    login_result = AgentThreadLoginResult(
        agent=agent,
        process=process,
        thread=thread,
        provider=provider_slug,
        terminal_id=terminal_identifier,
        session=AgentThreadLoginSession(
            session_id=bound_session_id,
            data=session_payload if isinstance(session_payload, dict) else None,
        ),
        descriptor_path=bind_payload.get("descriptor_path"),
        participants_path=bind_payload.get("participants_path"),
        metadata=bind_payload.get("metadata"),
        env=bind_payload.get("env"),
        provider_metadata=bind_payload.get("provider_metadata"),
        receipts=operation_receipts,
        journal=operation_journal,
    )
    return login_result.model_dump(mode="json")


__all__ = ["signup", "login", "session_update"]
