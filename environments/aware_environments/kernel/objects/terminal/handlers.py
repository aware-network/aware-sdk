"""Kernel handlers for terminal lifecycle operations."""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from aware_terminal_providers.core.descriptor import (
    ProviderDescriptorModel,
    ProviderReleaseNotesModel,
)

from ..agent_thread.session_ops import session_update as agent_thread_session_update
from aware_environment.fs import EnsureInstruction, MoveInstruction, OperationContext, OperationPlan
from .write_plan import (
    TerminalPlanResult,
    plan_descriptor_write,
    plan_participants_manifest,
    plan_pane_manifest,
)
from .models import TerminalDescriptorModel
from ..thread.fs import ThreadFSAdapter
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
from .._shared.timeline import ensure_datetime
from .._shared.fs_utils import ensure_iso_timestamp, write_json_atomic
from .descriptors import (
    delete_descriptor,
    descriptor_path,
    list_descriptors,
    load_descriptor,
    normalise_env,
    terminals_dir,
    write_descriptor,
)


def _import_runtime_module():
    try:
        return __import__("aware_terminal.runtime", fromlist=["runtime"])
    except ModuleNotFoundError:  # pragma: no cover - tooling fallback
        repo_root = Path(__file__).resolve().parents[5]
        tools_path = repo_root / "tools" / "terminal"
        if tools_path.exists():
            sys.path.append(str(tools_path))
        return __import__("aware_terminal.runtime", fromlist=["runtime"])


_runtime_mod = _import_runtime_module()

EnsureProviderSessionResult = getattr(_runtime_mod, "EnsureProviderSessionResult")
LifecycleResult = getattr(_runtime_mod, "LifecycleResult", None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _thread_identifier(entry) -> str:
    identifier = getattr(entry, "thread_id", None)
    if identifier:
        return identifier
    process_slug = getattr(entry, "process_slug", None)
    thread_slug = getattr(entry, "thread_slug", None)
    if process_slug and thread_slug:
        return f"{process_slug}/{thread_slug}"
    raise ValueError("Unable to derive thread identifier from entry.")


def _generate_terminal_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"term-{timestamp}-{suffix}"


def _stringify_env(env: Dict[str, Any]) -> Dict[str, str]:
    return {key: str(value) for key, value in env.items()}


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {k: _json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(v) for v in value]
        return str(value)


def _normalize_metadata_strings(metadata: Dict[str, Any]) -> Dict[str, str]:
    normalised: Dict[str, str] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, str):
            normalised[key] = value
        elif isinstance(value, (int, float, bool)):
            normalised[key] = str(value)
        else:
            normalised[key] = json.dumps(_json_safe(value))
    return normalised


def _build_provider_descriptor(provider_slug: str, result: EnsureProviderSessionResult) -> ProviderDescriptorModel:
    payload: Dict[str, Any] = dict(getattr(result, "metadata", {}) or {})
    payload["slug"] = provider_slug
    payload["session_id"] = getattr(result, "session_id", None)
    payload["updated_at"] = payload.get("updated_at") or _now_iso()
    env_payload = getattr(result, "env", None) or {}
    payload["env"] = _stringify_env(env_payload)

    if "version" not in payload:
        version_candidate = payload.get("channel_version") or payload.get("binary_version")
        if version_candidate:
            payload["version"] = version_candidate
    if "channel" not in payload and payload.get("channel_version"):
        payload["channel"] = payload.get("channel_version")

    release_notes_payload = payload.get("release_notes")
    if isinstance(release_notes_payload, str):
        payload["release_notes"] = {"summary": release_notes_payload}
    elif isinstance(release_notes_payload, dict):
        try:
            payload["release_notes"] = ProviderReleaseNotesModel.model_validate(release_notes_payload).model_dump(
                mode="json"
            )
        except Exception:
            payload["release_notes"] = release_notes_payload

    try:
        descriptor = ProviderDescriptorModel.model_validate(payload)
    except Exception:
        descriptor = ProviderDescriptorModel(
            slug=provider_slug,
            session_id=payload.get("session_id"),
            version=payload.get("version"),
            channel=payload.get("channel"),
            binary_path=payload.get("binary_path"),
            env=payload.get("env"),
            release_notes=None,
            updated_at=payload.get("updated_at"),
        )
    return descriptor


def _provider_metadata_summary(descriptor: ProviderDescriptorModel) -> Dict[str, str]:
    summary: Dict[str, str] = {
        "provider": descriptor.slug,
        "provider_session_id": descriptor.session_id,
    }
    if descriptor.version:
        summary["provider_version"] = descriptor.version
    if descriptor.channel:
        summary["provider_channel"] = descriptor.channel
    return summary


def _descriptor_touch(
    descriptor: TerminalDescriptorModel,
    *,
    session_id: Optional[str] = None,
    tmux_window: Optional[str] = None,
) -> TerminalDescriptorModel:
    payload: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if session_id is not None:
        payload["session_id"] = session_id
    if tmux_window is not None:
        payload["tmux_window"] = tmux_window
    return descriptor.model_copy(update=payload)


def _descriptor_bind_provider(
    descriptor: TerminalDescriptorModel,
    *,
    apt_id: Optional[str],
    provider: ProviderDescriptorModel,
    env: Optional[Dict[str, Any]],
    metadata: Optional[Dict[str, str]],
) -> TerminalDescriptorModel:
    merged_env = dict(descriptor.env)
    if env:
        for key, value in env.items():
            merged_env[key] = str(value)
    merged_metadata = dict(descriptor.metadata)
    if metadata:
        merged_metadata.update(metadata)
    return descriptor.model_copy(
        update={
            "apt_id": apt_id,
            "provider": provider,
            "env": merged_env,
            "metadata": merged_metadata,
            "updated_at": datetime.now(timezone.utc),
        }
    )


def _load_participants(adapter: ThreadFSAdapter, entry) -> ThreadParticipantsManifest:
    manifest = adapter.load_participants_manifest(entry)
    return manifest


def _participants_path(entry) -> Path:
    directory = Path(getattr(entry, "directory"))
    return directory / "participants.json"


def _require_agent_participant(manifest: ThreadParticipantsManifest, participant_id: str) -> ThreadParticipant:
    for participant in manifest.participants:
        if participant.participant_id == participant_id:
            if participant.type is not ThreadParticipantType.AGENT:
                raise ValueError("Terminal operations require agent participants.")
            return participant
    raise ValueError(f"Participant '{participant_id}' not found. Bind the agent before managing terminal sessions.")


def _serialize_participant(participant: ThreadParticipant) -> Dict[str, Any]:
    data = participant.model_dump(mode="json")
    if participant.last_seen:
        data["last_seen"] = ensure_iso_timestamp(participant.last_seen)
    return data


def _update_participant(manifest: ThreadParticipantsManifest, participant: ThreadParticipant) -> None:
    manifest.participants = [
        participant if existing.participant_id == participant.participant_id else existing
        for existing in manifest.participants
    ]


def _apply_agent_session_result(
    adapter: ThreadFSAdapter,
    entry,
    manifest: ThreadParticipantsManifest,
    participant: ThreadParticipant,
    *,
    provider_slug: str,
    metadata: Dict[str, str],
    identities_root: Path,
    session_result: EnsureProviderSessionResult,
    terminal_id: str,
) -> Tuple[ThreadParticipantsManifest, ThreadParticipant, str]:
    session = ThreadParticipantSession(
        session_id=session_result.session_id,
        transport=str(getattr(session_result, "socket_path", None)),
        state=ThreadParticipantSessionState.RUNNING,
        tmux_window=getattr(session_result, "tmux_window", None),
        socket_path=str(getattr(session_result, "socket_path", None)) if getattr(session_result, "socket_path", None) else None,
    )
    participant = participant.model_copy(
        update={
            "status": ThreadParticipantStatus.ATTACHED,
            "session": session,
            "metadata": metadata,
            "last_seen": datetime.now(timezone.utc),
        }
    )
    _update_participant(manifest, participant)
    participants_plan, participants_path_obj = plan_participants_manifest(
        entry,
        function_name="bind-provider",
        manifest=manifest,
    )
    plans = [participants_plan]

    identity = participant.identity
    if isinstance(identity, ThreadParticipantIdentityAgent):
        slug_value = identity.slug or ""
        parts = slug_value.split("/")
        if len(parts) == 3:
            agent, process, thread = parts
            update_payload = agent_thread_session_update(
                Path(identities_root),
                agent=agent,
                process=process,
                thread=thread,
                session_id=getattr(session_result, "session_id", None),
                provider=provider_slug,
                terminal_id=terminal_id,
            )
            if hasattr(update_payload, "plan"):
                plan_obj = getattr(update_payload, "plan", None)
                if plan_obj is not None:
                    plans.append(plan_obj)

    participants_path = str(participants_path_obj.resolve())
    return manifest, participant, participants_path, tuple(plans)


def _ensure_session(
    *,
    thread_identifier: str,
    apt_id: str,
    provider: str,
    resume: bool,
    existing_session_id: Optional[str],
    terminal_id: Optional[str],
) -> EnsureProviderSessionResult:
    return _runtime_mod.ensure_provider_session(
        thread=thread_identifier,
        provider_slug=provider,
        apt_id=apt_id,
        resume=resume,
        existing_session_id=existing_session_id,
        terminal_id=terminal_id,
    )


def _build_terminal_pane_plan(
    entry,
    *,
    descriptor: Dict[str, Any],
    descriptor_path_value: Path,
    socket_path: Optional[Path],
    function_name: str,
) -> Tuple[OperationPlan, Path]:
    pane_kind = f"terminal-{descriptor['id']}"
    payload = OrderedDict(
        {
            "thread_id": descriptor["thread_id"],
            "terminal_id": descriptor["id"],
            "name": descriptor.get("name"),
            "descriptor_path": str(descriptor_path_value),
            "session_id": descriptor.get("session_id"),
            "tmux_window": descriptor.get("tmux_window"),
            "socket_path": str(socket_path) if socket_path else None,
            "cwd": descriptor.get("cwd"),
            "shell": descriptor.get("shell"),
            "apt_id": descriptor.get("apt_id"),
            "provider": descriptor.get("provider"),
            "env": descriptor.get("env"),
            "metadata": descriptor.get("metadata"),
        }
    )
    pane_plan, _, manifest_path, _, _ = plan_pane_manifest(
        entry,
        function_name=function_name,
        pane_kind=pane_kind,
        branch_data={
            "name": descriptor.get("name"),
            "pane_kind": pane_kind,
            "is_main": False,
        },
        pane_payload=payload,
        manifest_version=1,
    )
    return pane_plan, manifest_path


def create_terminal(
    runtime_root: Path,
    aware_root: Path,
    *,
    thread_identifier: str,
    terminal_id: Optional[str] = None,
    name: Optional[str] = None,
    cwd: Optional[Path] = None,
    shell: str = "/bin/bash",
    env: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    adapter = ThreadFSAdapter(Path(runtime_root))
    entry = adapter.get_thread(thread_identifier)
    if entry is None:
        raise ValueError(f"Thread '{thread_identifier}' not found under {runtime_root}.")

    resolved_thread_id = _thread_identifier(entry)
    term_id = terminal_id or _generate_terminal_id()
    descriptor_path_value = descriptor_path(aware_root, resolved_thread_id, term_id)

    if load_descriptor(descriptor_path_value):
        raise ValueError(f"Terminal '{term_id}' already exists for thread '{resolved_thread_id}'.")

    env_map = normalise_env(env)
    cwd_path = Path(cwd).expanduser().resolve() if cwd else Path.cwd()

    result = _runtime_mod.ensure_terminal_session(
        thread=resolved_thread_id,
        terminal_id=term_id,
        cwd=cwd_path,
        shell=shell or "/bin/bash",
    )

    now = datetime.now(timezone.utc)
    descriptor_model = TerminalDescriptorModel(
        id=term_id,
        thread_id=resolved_thread_id,
        name=name or term_id,
        cwd=cwd_path,
        shell=shell or "/bin/bash",
        env=env_map,
        session_id=getattr(result, "session_id", None),
        tmux_window=getattr(result, "tmux_window", None),
        created_at=now,
        updated_at=now,
        metadata={},
    )
    descriptor_payload = descriptor_model.model_dump(mode="json")

    descriptor_plan = plan_descriptor_write(
        function_name="create",
        descriptor_path=descriptor_path_value,
        descriptor=descriptor_payload,
        thread_id=resolved_thread_id,
        terminal_id=term_id,
        event="created",
    )
    socket_path = getattr(result, "socket_path", None)
    pane_plan, _ = _build_terminal_pane_plan(
        entry,
        descriptor=descriptor_payload,
        descriptor_path_value=descriptor_path_value,
        socket_path=Path(socket_path) if socket_path else None,
        function_name="create",
    )

    payload = {
        "thread_id": resolved_thread_id,
        "descriptor_path": str(descriptor_path_value),
        "terminal": descriptor_payload,
        "session": {
            "session_id": getattr(result, "session_id", None),
            "tmux_window": getattr(result, "tmux_window", None),
            "socket_path": str(socket_path) if socket_path else None,
        },
    }
    return TerminalPlanResult(plans=(descriptor_plan, pane_plan), payload=payload)


def list_terminals(
    runtime_root: Path,
    aware_root: Path,
    *,
    thread_identifier: str,
) -> Dict[str, Any]:
    adapter = ThreadFSAdapter(Path(runtime_root))
    entry = adapter.get_thread(thread_identifier)
    if entry is None:
        raise ValueError(f"Thread '{thread_identifier}' not found under {runtime_root}.")

    resolved_thread_id = _thread_identifier(entry)
    descriptors_dir = terminals_dir(aware_root, resolved_thread_id)
    descriptors = list_descriptors(descriptors_dir)

    manifest = _load_participants(adapter, entry)
    session_lookup: Dict[str, ThreadParticipantSession] = {}
    if manifest.participants:
        for participant in manifest.participants:
            session = participant.session
            if session and session.session_id:
                session_lookup[session.session_id] = session

    entries: list[Dict[str, Any]] = []
    for descriptor_model in descriptors:
        session_key = descriptor_model.session_id or descriptor_model.id
        session = session_lookup.get(session_key)
        status = "running" if session else "detached"
        tmux_window = session.tmux_window if session else descriptor_model.tmux_window
        socket_path = descriptor_model.metadata.get("socket_path") if isinstance(descriptor_model.metadata, dict) else None
        entry_payload: Dict[str, Any] = {
            "id": descriptor_model.id,
            "name": descriptor_model.name,
            "status": status,
            "session_id": session.session_id if session else descriptor_model.session_id,
            "tmux_window": tmux_window,
            "socket_path": socket_path if session else None,
            "descriptor_path": str(descriptor_path(aware_root, resolved_thread_id, descriptor_model.id)),
            "cwd": str(descriptor_model.cwd),
            "shell": descriptor_model.shell,
            "created_at": ensure_iso_timestamp(descriptor_model.created_at),
            "updated_at": ensure_iso_timestamp(descriptor_model.updated_at),
            "apt_id": descriptor_model.apt_id,
            "provider_slug": descriptor_model.provider.slug if descriptor_model.provider else None,
        }
        entries.append(entry_payload)

    payload: Dict[str, Any] = {
        "thread_id": resolved_thread_id,
        "count": len(entries),
        "terminals": entries,
    }
    return payload


def attach_terminal(
    runtime_root: Path,
    aware_root: Path,
    *,
    thread_identifier: str,
    terminal_id: str,
    cwd: Optional[Path] = None,
    shell: Optional[str] = None,
) -> TerminalPlanResult:
    adapter = ThreadFSAdapter(Path(runtime_root))
    entry = adapter.get_thread(thread_identifier)
    if entry is None:
        raise ValueError(f"Thread '{thread_identifier}' not found under {runtime_root}.")

    resolved_thread_id = _thread_identifier(entry)
    descriptor_path_value = descriptor_path(aware_root, resolved_thread_id, terminal_id)
    descriptor_model = load_descriptor(descriptor_path_value)
    if descriptor_model is None:
        now = datetime.now(timezone.utc)
        descriptor_model = TerminalDescriptorModel(
            id=terminal_id,
            thread_id=resolved_thread_id,
            name=terminal_id,
            cwd=Path.cwd(),
            shell=shell or "/bin/bash",
            env={},
            metadata={},
            created_at=now,
            updated_at=now,
        )

    env_payload = dict(descriptor_model.env)
    metadata_payload = dict(descriptor_model.metadata)
    cwd_path = Path(cwd).expanduser().resolve() if cwd else Path(descriptor_model.cwd)
    shell_value = shell or descriptor_model.shell or "/bin/bash"

    result = _runtime_mod.ensure_terminal_session(
        thread=resolved_thread_id,
        terminal_id=terminal_id,
        cwd=cwd_path,
        shell=shell_value,
    )
    descriptor_model = descriptor_model.model_copy(
        update={
            "cwd": cwd_path,
            "shell": shell_value,
            "env": env_payload,
            "metadata": metadata_payload,
        }
    )
    descriptor_model = _descriptor_touch(
        descriptor_model,
        session_id=getattr(result, "session_id", None),
        tmux_window=getattr(result, "tmux_window", None),
    ).model_copy(update={"last_attached_at": datetime.now(timezone.utc)})

    descriptor_plan = plan_descriptor_write(
        function_name="attach",
        descriptor_path=descriptor_path_value,
        descriptor=descriptor_model.model_dump(mode="json"),
        thread_id=resolved_thread_id,
        terminal_id=terminal_id,
        event="modified",
    )

    socket_path = getattr(result, "socket_path", None)
    pane_plan, _ = _build_terminal_pane_plan(
        entry,
        descriptor=descriptor_model.model_dump(mode="json"),
        descriptor_path_value=descriptor_path_value,
        socket_path=Path(socket_path) if socket_path else None,
        function_name="attach",
    )

    payload = {
        "thread_id": resolved_thread_id,
        "terminal_id": terminal_id,
        "descriptor_path": str(descriptor_path_value),
        "terminal": descriptor_model.model_dump(mode="json"),
        "session": {
            "session_id": getattr(result, "session_id", None),
            "tmux_window": getattr(result, "tmux_window", None),
            "socket_path": str(socket_path) if socket_path else None,
        },
    }
    return TerminalPlanResult(plans=(descriptor_plan, pane_plan), payload=payload)


def ensure_terminal_session(
    runtime_root: Path,
    aware_root: Path,
    identities_root: Path,
    *,
    thread_identifier: str,
    apt_id: str,
    provider: str,
    resume: bool,
    metadata: Optional[Dict[str, Any]] = None,
    terminal_id: Optional[str] = None,
) -> TerminalPlanResult:
    adapter = ThreadFSAdapter(Path(runtime_root))
    entry = adapter.get_thread(thread_identifier)
    if entry is None:
        raise ValueError(f"Thread '{thread_identifier}' not found under {runtime_root}.")

    resolved_thread_id = _thread_identifier(entry)
    manifest = _load_participants(adapter, entry)
    participant = _require_agent_participant(manifest, apt_id)

    metadata_payload: Dict[str, str] = dict(participant.metadata or {})
    metadata_payload.update(_normalize_metadata_strings(metadata or {}))
    metadata_payload["provider"] = provider
    if terminal_id:
        metadata_payload.setdefault("terminal_id", terminal_id)

    descriptor_path_value: Optional[Path] = None
    descriptor_model: Optional[TerminalDescriptorModel] = None
    if terminal_id:
        descriptor_path_value = descriptor_path(aware_root, resolved_thread_id, terminal_id)
        descriptor_model = load_descriptor(descriptor_path_value)
        if descriptor_model is None:
            now = datetime.now(timezone.utc)
            descriptor_model = TerminalDescriptorModel(
                id=terminal_id,
                thread_id=resolved_thread_id,
                name=terminal_id,
                cwd=Path.cwd(),
                shell="/bin/bash",
                env={},
                metadata={},
                created_at=now,
                updated_at=now,
            )

    existing_session_id = participant.session.session_id if participant.session else None
    if not existing_session_id and descriptor_model and descriptor_model.provider:
        existing_session_id = descriptor_model.provider.session_id

    result = _ensure_session(
        thread_identifier=resolved_thread_id,
        apt_id=apt_id,
        provider=provider,
        resume=resume,
        existing_session_id=existing_session_id,
        terminal_id=terminal_id,
    )

    plans: list[OperationPlan] = []

    if descriptor_path_value and descriptor_model is not None:
        provider_descriptor = _build_provider_descriptor(provider, result)
        descriptor_metadata = _provider_metadata_summary(provider_descriptor)
        descriptor_metadata["terminal_id"] = descriptor_model.id
        descriptor_metadata = _normalize_metadata_strings(descriptor_metadata)

        metadata_payload.update(descriptor_metadata)

        descriptor_model = _descriptor_bind_provider(
            descriptor_model,
            apt_id=apt_id,
            provider=provider_descriptor,
            env=getattr(result, "env", None),
            metadata=descriptor_metadata,
        )

        descriptor_plan = plan_descriptor_write(
            function_name="ensure-session",
            descriptor_path=descriptor_path_value,
            descriptor=descriptor_model.model_dump(mode="json"),
            thread_id=resolved_thread_id,
            terminal_id=descriptor_model.id,
            event="modified",
        )
        plans.append(descriptor_plan)

        socket_path = getattr(result, "socket_path", None)
        pane_plan, _ = _build_terminal_pane_plan(
            entry,
            descriptor=descriptor_model.model_dump(mode="json"),
            descriptor_path_value=descriptor_path_value,
            socket_path=Path(socket_path) if socket_path else None,
            function_name="ensure-session",
        )
        plans.append(pane_plan)

    manifest, participant, participants_path, participant_plans = _apply_agent_session_result(
        adapter,
        entry,
        manifest,
        participant,
        provider_slug=provider,
        metadata=metadata_payload,
        identities_root=identities_root,
        session_result=result,
        terminal_id=terminal_id or apt_id,
    )
    plans.extend(participant_plans)

    payload: Dict[str, Any] = {
        "thread_id": manifest.thread_id,
        "participant": _serialize_participant(participant),
        "provider": provider,
        "session_id": getattr(result, "session_id", None),
        "socket_path": str(getattr(result, "socket_path", None)),
        "participants_path": participants_path,
        "updated_at": ensure_iso_timestamp(manifest.updated_at),
        "metadata": metadata_payload,
        "env": getattr(result, "env", None),
        "provider_metadata": _json_safe(getattr(result, "metadata", None)),
    }
    if descriptor_model is not None and descriptor_path_value is not None:
        payload["terminal_id"] = descriptor_model.id
        payload["descriptor_path"] = str(descriptor_path_value)
        payload["terminal"] = descriptor_model.model_dump(mode="json")

    return TerminalPlanResult(plans=tuple(plans), payload=payload)


def delete_terminal(
    runtime_root: Path,
    aware_root: Path,
    *,
    thread_identifier: str,
    terminal_id: str,
    remove_session: bool = False,
    kill_window: bool = False,
) -> TerminalPlanResult:
    adapter = ThreadFSAdapter(Path(runtime_root))
    entry = adapter.get_thread(thread_identifier)
    if entry is None:
        raise ValueError(f"Thread '{thread_identifier}' not found under {runtime_root}.")

    resolved_thread_id = _thread_identifier(entry)
    descriptor_path_value = descriptor_path(aware_root, resolved_thread_id, terminal_id)
    descriptor_model = load_descriptor(descriptor_path_value)
    if descriptor_model is None:
        raise ValueError(f"Terminal '{terminal_id}' not found for thread '{resolved_thread_id}'.")

    manifest = _load_participants(adapter, entry)
    session_identifier = descriptor_model.session_id
    participant_updated = False
    if remove_session and session_identifier and manifest.participants:
        updated_participants = []
        for participant in manifest.participants:
            if (
                participant.session
                and participant.session.session_id == session_identifier
            ):
                updated_participants.append(
                    participant.model_copy(
                        update={
                            "session": None,
                            "status": ThreadParticipantStatus.DETACHED,
                            "last_seen": datetime.now(timezone.utc),
                        }
                    )
                )
                participant_updated = True
            else:
                updated_participants.append(participant)
        manifest.participants = updated_participants

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    def _archive_path(original: Path) -> Optional[Path]:
        original = Path(original)
        if not original.exists():
            return None
        archive_dir = original.parent / ".deleted"
        unique_suffix = uuid.uuid4().hex[:8]
        archive_name = f"{original.stem}-{timestamp}-{unique_suffix}{original.suffix}"
        return archive_dir / archive_name

    descriptor_archive = _archive_path(descriptor_path_value)
    pane_kind = f"terminal-{terminal_id}"
    branch_path = adapter._branch_file(entry, pane_kind)
    pane_path = adapter._pane_manifest_file(entry, pane_kind)
    branch_archive = _archive_path(branch_path)
    pane_archive = _archive_path(pane_path)

    ensures: list[EnsureInstruction] = []
    moves: list[MoveInstruction] = []
    writes: list[WriteInstruction] = []

    for archive_path in (descriptor_archive, branch_archive, pane_archive):
        if archive_path is not None:
            ensures.append(EnsureInstruction(path=archive_path.parent))

    if descriptor_archive is not None:
        moves.append(MoveInstruction(src=descriptor_path_value, dest=descriptor_archive, overwrite=True))
    if branch_archive is not None and branch_path.exists():
        moves.append(MoveInstruction(src=branch_path, dest=branch_archive, overwrite=True))
    if pane_archive is not None and pane_path.exists():
        moves.append(MoveInstruction(src=pane_path, dest=pane_archive, overwrite=True))

    if participant_updated:
        participants_plan, _ = plan_participants_manifest(
            entry,
            function_name="delete",
            manifest=manifest,
        )
        plans_extra = getattr(participants_plan, "writes", None)
        ensures = list(ensures)
        ensures.extend(participants_plan.ensure_dirs)
        moves.extend(participants_plan.moves)
        writes.extend(participants_plan.writes)

    context = OperationContext(
        object_type="terminal",
        function="delete",
        selectors={"thread": resolved_thread_id, "terminal": terminal_id},
    )

    plan = OperationPlan(
        context=context,
        ensure_dirs=tuple(ensures),
        moves=tuple(moves),
        writes=tuple(writes),
    )

    payload = {
        "thread_id": resolved_thread_id,
        "terminal_id": terminal_id,
        "descriptor_path": str(descriptor_path_value),
        "descriptor_archive_path": str(descriptor_archive) if descriptor_archive else None,
        "branch_archive_path": str(branch_archive) if branch_archive else None,
        "pane_archive_path": str(pane_archive) if pane_archive else None,
        "removed_session": bool(participant_updated),
        "kill_window": kill_window,
        "session_id": session_identifier,
        "tmux_window": descriptor_model.tmux_window,
    }

    return TerminalPlanResult(plans=(plan,), payload=payload)


def session_resolve(
    runtime_root: Path,
    aware_root: Path,
    identities_root: Path,
    *,
    thread_identifier: str,
    provider: str,
    terminal_id: Optional[str] = None,
    apt_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not hasattr(_runtime_mod, "discover_provider_session"):
        return {
            "success": False,
            "error": "discover_provider_session_unavailable",
            "thread_id": thread_identifier,
            "provider": provider,
        }

    adapter = ThreadFSAdapter(Path(runtime_root))
    entry = adapter.get_thread(thread_identifier)
    if entry is None:
        raise ValueError(f"Thread '{thread_identifier}' not found under {runtime_root}.")

    resolved_thread_id = _thread_identifier(entry)

    try:
        result = _runtime_mod.discover_provider_session(
            resolved_thread_id,
            provider,
            terminal_id=terminal_id,
            apt_id=apt_id,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "thread_id": resolved_thread_id,
            "provider": provider,
        }

    success = bool(getattr(result, "success", False))
    message = getattr(result, "message", None)
    data = _json_safe(getattr(result, "data", None))

    payload = {
        "success": success,
        "message": message,
        "data": data,
        "thread_id": resolved_thread_id,
        "provider": provider,
        "aware_root": str(Path(aware_root).expanduser().resolve()),
        "runtime_root": str(Path(runtime_root).expanduser().resolve()),
        "identities_root": str(Path(identities_root).expanduser().resolve()),
    }
    if terminal_id:
        payload["terminal_id"] = terminal_id
    if apt_id:
        payload["apt_id"] = apt_id
    return payload


def bind_provider(
    runtime_root: Path,
    aware_root: Path,
    identities_root: Path,
    *,
    thread_identifier: str,
    terminal_id: str,
    apt_id: str,
    provider: Optional[str] = None,
    resume: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    adapter = ThreadFSAdapter(Path(runtime_root))
    entry = adapter.get_thread(thread_identifier)
    if entry is None:
        raise ValueError(f"Thread '{thread_identifier}' not found under {runtime_root}.")

    resolved_thread_id = _thread_identifier(entry)
    descriptor_path_value = descriptor_path(aware_root, resolved_thread_id, terminal_id)
    descriptor_model = load_descriptor(descriptor_path_value)
    if descriptor_model is None:
        now = datetime.now(timezone.utc)
        descriptor_model = TerminalDescriptorModel(
            id=terminal_id,
            thread_id=resolved_thread_id,
            name=terminal_id,
            cwd=Path.cwd(),
            shell="/bin/bash",
            env={},
            metadata={},
            created_at=now,
            updated_at=now,
        )

    manifest = _load_participants(adapter, entry)
    participant = _require_agent_participant(manifest, apt_id)

    metadata_payload: Dict[str, Any] = dict(participant.metadata or {})
    if metadata:
        metadata_payload.update(metadata)
    metadata_payload["terminal_id"] = terminal_id

    provider_slug = provider or metadata_payload.get("provider")
    if not provider_slug and descriptor_model.provider:
        provider_slug = descriptor_model.provider.slug
    if not provider_slug:
        raise ValueError("Provider not specified. Supply provider argument when binding terminal.")
    metadata_payload["provider"] = provider_slug

    existing_session_id = participant.session.session_id if participant.session else None
    if not existing_session_id:
        if descriptor_model.provider:
            existing_session_id = descriptor_model.provider.session_id

    result = _ensure_session(
        thread_identifier=resolved_thread_id,
        apt_id=apt_id,
        provider=provider_slug,
        resume=resume,
        existing_session_id=existing_session_id,
        terminal_id=terminal_id,
    )

    provider_descriptor = _build_provider_descriptor(provider_slug, result)
    descriptor_metadata = _provider_metadata_summary(provider_descriptor)
    descriptor_metadata["terminal_id"] = terminal_id
    descriptor_metadata = _normalize_metadata_strings(descriptor_metadata)

    descriptor_model = _descriptor_bind_provider(
        descriptor_model,
        apt_id=apt_id,
        provider=provider_descriptor,
        env=getattr(result, "env", None),
        metadata=descriptor_metadata,
    )
    descriptor_plan = plan_descriptor_write(
        function_name="bind-provider",
        descriptor_path=descriptor_path_value,
        descriptor=descriptor_model.model_dump(mode="json"),
        thread_id=resolved_thread_id,
        terminal_id=terminal_id,
        event="modified",
    )
    plans = [descriptor_plan]

    metadata_payload.update(descriptor_metadata)
    metadata_payload = _normalize_metadata_strings(metadata_payload)

    manifest, participant, participants_path, participant_plans = _apply_agent_session_result(
        adapter,
        entry,
        manifest,
        participant,
        provider_slug=provider_slug,
        metadata=metadata_payload,
        identities_root=identities_root,
        session_result=result,
        terminal_id=terminal_id,
    )
    plans.extend(participant_plans)

    socket_path = getattr(result, "socket_path", None)
    pane_plan, _ = _build_terminal_pane_plan(
        entry,
        descriptor=descriptor_model.model_dump(mode="json"),
        descriptor_path_value=descriptor_path_value,
        socket_path=Path(socket_path) if socket_path else None,
        function_name="bind-provider",
    )
    plans.append(pane_plan)

    payload: Dict[str, Any] = {
        "thread_id": manifest.thread_id,
        "terminal_id": terminal_id,
        "descriptor_path": str(descriptor_path_value),
        "participant": _serialize_participant(participant),
        "provider": provider_slug,
        "provider_descriptor": provider_descriptor.model_dump(mode="json"),
        "session_id": getattr(result, "session_id", None),
        "socket_path": str(socket_path) if socket_path else None,
        "participants_path": participants_path,
        "updated_at": ensure_iso_timestamp(manifest.updated_at),
        "metadata": metadata_payload,
        "env": getattr(result, "env", None),
        "provider_metadata": _json_safe(getattr(result, "metadata", None)),
    }
    return TerminalPlanResult(plans=tuple(plans), payload=payload)


__all__ = [
    "attach_terminal",
    "bind_provider",
    "create_terminal",
    "session_resolve",
]
