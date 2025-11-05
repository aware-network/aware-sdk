"""Helper utilities for agent identity operations."""

from __future__ import annotations

import json
import os
import warnings
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .._shared.fs_utils import _safe_load_json

_TERMINAL_RUNTIME_MODULE = None  # cached import


def _resolve_identities_root(value: Path | str | None) -> Path:
    if value is None:
        return (Path("docs") / "identities").resolve()
    path = Path(value).expanduser()
    return path.resolve()


def _metadata_from_env() -> Dict[str, Optional[str]]:
    env = os.environ
    return {
        "agent": env.get("AWARE_AGENT"),
        "process": env.get("AWARE_PROCESS"),
        "thread": env.get("AWARE_THREAD"),
        "apt_id": env.get("APT_ID") or env.get("AWARE_APT_ID"),
        "terminal_id": env.get("AWARE_TERMINAL_ID"),
        "provider": env.get("AWARE_PROVIDER"),
        "provider_session": env.get("AWARE_PROVIDER_SESSION_ID") or env.get("AWARE_SESSION_ID"),
    }


def _infer_from_cwd(identities_root: Path) -> Dict[str, Optional[str]]:
    cwd = Path.cwd().resolve()
    try:
        relative = cwd.relative_to(identities_root)
    except ValueError:
        return {"agent": None, "process": None, "thread": None}

    parts = relative.parts
    agent = process = thread = None
    if len(parts) >= 2 and parts[0] == "agents":
        agent = parts[1]
    if len(parts) >= 5 and parts[2:4] == ("runtime", "process"):
        process = parts[4]
    if len(parts) >= 7 and parts[5] == "threads":
        thread = parts[6]
    return {"agent": agent, "process": process, "thread": thread}


def _format_identity_paths(
    identities_root: Path,
    agent_slug: Optional[str],
    process_slug: Optional[str],
    thread_slug: Optional[str],
) -> Dict[str, Path]:
    paths: Dict[str, Path] = {}
    if agent_slug:
        paths["agent"] = identities_root / "agents" / agent_slug
    if agent_slug and process_slug:
        paths["process"] = identities_root / "agents" / agent_slug / "runtime" / "process" / process_slug
    if agent_slug and process_slug and thread_slug:
        paths["thread"] = (
            identities_root / "agents" / agent_slug / "runtime" / "process" / process_slug / "threads" / thread_slug
        )
    return paths


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    data = _safe_load_json(path)
    if data is None:
        warnings.warn(f"Failed to parse JSON at {path}", RuntimeWarning)
    return data if isinstance(data, dict) else None


def _resolve_roles_from_thread(thread_doc: Optional[dict]) -> Dict[str, List[str]]:
    if not thread_doc:
        return {"roles": [], "policies": []}
    roles = list(thread_doc.get("roles", []) or [])
    policies = list(thread_doc.get("policies", []) or [])
    return {"roles": roles, "policies": policies}


def _aware_home() -> Path:
    custom = os.environ.get("AWARE_HOME")
    if custom:
        return Path(custom).expanduser().resolve()
    return (Path.home() / ".aware").resolve()


def _get_terminal_runtime_module():
    global _TERMINAL_RUNTIME_MODULE
    if _TERMINAL_RUNTIME_MODULE is None:
        try:
            _TERMINAL_RUNTIME_MODULE = import_module("aware_terminal.runtime.session")
        except Exception:  # pragma: no cover - optional dependency
            _TERMINAL_RUNTIME_MODULE = False
    return _TERMINAL_RUNTIME_MODULE if _TERMINAL_RUNTIME_MODULE is not False else None


def _discover_session_via_runtime(
    thread_identifier: Optional[str],
    provider_slug: Optional[str],
    *,
    terminal_id: Optional[str],
    apt_id: Optional[str],
) -> Dict[str, Optional[object]]:
    if not thread_identifier or not provider_slug:
        return {"success": False, "message": "Missing thread or provider context.", "data": None}

    runtime = _get_terminal_runtime_module()
    if runtime is None or not hasattr(runtime, "discover_provider_session"):
        return {"success": False, "message": "Terminal runtime session discovery unavailable.", "data": None}

    try:
        result = runtime.discover_provider_session(
            thread_identifier,
            provider_slug,
            terminal_id=terminal_id,
            apt_id=apt_id,
        )
    except Exception as exc:  # pragma: no cover - external dependency
        return {"success": False, "message": str(exc), "data": None}

    success = bool(getattr(result, "success", False))
    data = getattr(result, "data", None)
    message = getattr(result, "message", None)
    return {"success": success, "data": data, "message": message}


def _resolver_context(
    env_data: Dict[str, Optional[str]],
    thread_doc: Optional[dict],
    expected_thread_identifier: Optional[str],
) -> Dict[str, Optional[str]]:
    metadata: Dict[str, str] = {}
    if thread_doc and isinstance(thread_doc.get("metadata"), dict):
        metadata = dict(thread_doc["metadata"])

    provider = env_data.get("provider") or metadata.get("terminal_provider") or metadata.get("provider")
    terminal_id = env_data.get("terminal_id") or metadata.get("terminal_id")
    apt_id = env_data.get("apt_id") or (thread_doc.get("id") if isinstance(thread_doc, dict) else None)

    return {
        "provider": provider,
        "terminal_id": terminal_id,
        "apt_id": apt_id,
        "thread_identifier": expected_thread_identifier,
    }


def _runtime_root() -> Path:
    runtime_env = os.environ.get("AWARE_RUNTIME_ROOT")
    if runtime_env:
        return Path(runtime_env).expanduser().resolve()
    return (Path("docs") / "runtime" / "process").resolve()


def _session_receipt(session_id: str) -> Optional[dict]:
    path = _aware_home() / "sessions" / f"{session_id}.json"
    data = _safe_load_json(path)
    return data if isinstance(data, dict) else None


def _all_session_receipts() -> List[dict]:
    sessions_dir = _aware_home() / "sessions"
    if not sessions_dir.exists():
        return []
    receipts: List[dict] = []
    for path in sorted(sessions_dir.glob("*.json")):
        if path.name == "current_session.json":
            continue
        data = _safe_load_json(path)
        if isinstance(data, dict):
            receipts.append(data)
    return receipts


def _resolve_thread_identity_from_runtime(thread_uuid: str) -> Optional[Dict[str, Optional[str]]]:
    if not thread_uuid:
        return None
    root = _runtime_root()
    if not root.exists():
        return None

    for process_dir in sorted(root.iterdir()):
        threads_dir = process_dir / "threads"
        if not threads_dir.is_dir():
            continue
        for manifest_path in threads_dir.glob("*/participants.json"):
            data = _read_json(manifest_path)
            if not data or data.get("thread_id") != thread_uuid:
                continue
            participants = data.get("participants") or []
            for participant in participants:
                identity = participant.get("identity") or {}
                slug = identity.get("slug")
                if not slug:
                    continue
                parts = slug.split("/")
                if len(parts) == 3:
                    agent_slug, process_slug, thread_slug = parts
                else:
                    agent_slug = identity.get("agent_handle") or identity.get("agent_slug")
                    process_slug = data.get("process_slug")
                    thread_slug = slug
                return {
                    "agent_slug": agent_slug,
                    "process_slug": process_slug or data.get("process_slug"),
                    "thread_slug": thread_slug,
                    "agent_uuid": identity.get("agent_id"),
                    "process_uuid": identity.get("agent_process_id"),
                    "thread_uuid": data.get("thread_id"),
                    "actor_id": identity.get("actor_id"),
                }
    return None


def _merge_session_receipts(
    payload: dict,
    receipts: List[dict],
    env_data: Dict[str, Optional[str]],
    expected_thread_id: Optional[str],
    expected_thread_uuid: Optional[str],
    warnings_list: List[str],
) -> List[str]:
    extra_sources: List[str] = []
    if not receipts:
        return extra_sources

    terminal_payload = payload.get("terminal") or {}
    sessions_summary: List[dict] = []
    expected_thread_ids = {
        value for value in (expected_thread_id, expected_thread_uuid) if isinstance(value, str) and value
    }
    identity_by_thread: Dict[str, Dict[str, Optional[str]]] = {}

    for entry in receipts:
        session_id = entry.get("session_id")
        session_thread = entry.get("thread_id")
        if expected_thread_ids and session_thread and session_thread not in expected_thread_ids:
            warnings_list.append(
                f"Session '{session_id}' thread '{session_thread}' does not match resolved thread '{expected_thread_id}'."
            )
        if session_thread and session_thread not in identity_by_thread:
            resolved = _resolve_thread_identity_from_runtime(session_thread)
            if resolved:
                identity_by_thread[session_thread] = resolved
        sessions_summary.append(
            {
                "session_id": session_id,
                "status": entry.get("status"),
                "provider": entry.get("provider"),
                "terminal_id": entry.get("terminal_id"),
                "created_at": entry.get("created_at"),
                "updated_at": entry.get("updated_at"),
            }
        )

    if sessions_summary:
        terminal_payload.setdefault("sessions", sessions_summary)

    target_thread = payload.get("thread") or {}
    target_thread_slug = target_thread.get("slug")
    target_thread_uuid = target_thread.get("uuid")
    target_thread_ids = {
        value
        for value in (
            target_thread_slug if isinstance(target_thread_slug, str) else None,
            target_thread_uuid if isinstance(target_thread_uuid, str) else None,
        )
        if value
    }

    def _entry_rank(entry: dict) -> tuple[int, str]:
        score = 0
        thread_id = entry.get("thread_id")
        if expected_thread_ids and thread_id in expected_thread_ids:
            score += 4
        identity = identity_by_thread.get(thread_id) or {}
        identity_slug = identity.get("thread_slug")
        identity_uuid = identity.get("thread_uuid")
        if identity_slug and identity_slug in target_thread_ids:
            score += 2
        if identity_uuid and identity_uuid in target_thread_ids:
            score += 2
        provider = entry.get("provider")
        if provider and provider == env_data.get("provider"):
            score += 1
        timestamp = entry.get("updated_at") or entry.get("created_at") or ""
        return (score, timestamp)

    ranked = sorted(
        ((entry, _entry_rank(entry)) for entry in receipts),
        key=lambda item: item[1],
        reverse=True,
    )
    primary_entry = ranked[0][0] if ranked else receipts[0]

    if not terminal_payload.get("provider"):
        terminal_payload["provider"] = primary_entry.get("provider")
    if (
        not terminal_payload.get("session_id")
        or (expected_thread_ids and primary_entry.get("thread_id") in expected_thread_ids)
    ):
        terminal_payload["session_id"] = primary_entry.get("session_id")
    if not terminal_payload.get("id") and primary_entry.get("terminal_id"):
        terminal_payload["id"] = primary_entry.get("terminal_id")

    for session_thread, identity in identity_by_thread.items():
        if not identity:
            continue
        if not payload.get("agent"):
            payload["agent"] = {"slug": identity.get("agent_slug"), "uuid": identity.get("agent_uuid")}
        if not payload.get("process"):
            payload["process"] = {"slug": identity.get("process_slug"), "uuid": identity.get("process_uuid")}
        if not payload.get("thread"):
            payload["thread"] = {"slug": identity.get("thread_slug"), "uuid": identity.get("thread_uuid")}
        extra_sources.append("runtime-participants")

    payload["terminal"] = terminal_payload
    return extra_sources


def _write_receipt(path: Optional[str], payload: dict) -> None:
    if not path:
        return
    receipt_path = Path(path).expanduser()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _build_whoami_payload(
    identities_root: Path,
    *,
    agent: Optional[str] = None,
    process: Optional[str] = None,
    thread: Optional[str] = None,
) -> dict:
    env_data = _metadata_from_env()
    sources: List[str] = []
    warnings_list: List[str] = []
    if any(env_data.values()):
        sources.append("env")

    if agent is not None:
        env_data["agent"] = agent
    if process is not None:
        env_data["process"] = process
    if thread is not None:
        env_data["thread"] = thread

    agent_slug = env_data.get("agent")
    process_slug = env_data.get("process")
    thread_slug = env_data.get("thread")

    if not agent_slug or not process_slug or not thread_slug:
        cwd_inferred = _infer_from_cwd(identities_root)
        if any(cwd_inferred.values()):
            sources.append("cwd")
            agent_slug = agent_slug or cwd_inferred.get("agent")
            process_slug = process_slug or cwd_inferred.get("process")
            thread_slug = thread_slug or cwd_inferred.get("thread")

    paths = _format_identity_paths(identities_root, agent_slug, process_slug, thread_slug)
    agent_doc = _read_json(paths["agent"] / "agent.json") if "agent" in paths else None
    process_doc = _read_json(paths["process"] / "process.json") if "process" in paths else None
    thread_dir = paths.get("thread")
    thread_doc = _read_json(thread_dir / "agent_process_thread.json") if thread_dir else None

    if any([agent_doc, process_doc, thread_doc]):
        sources.append("filesystem")

    roles_info = _resolve_roles_from_thread(thread_doc)

    payload: Dict[str, Any] = {
        "agent": {"slug": agent_slug, "uuid": agent_doc.get("id") if agent_doc else None} if agent_slug else None,
        "process": (
            {"slug": process_slug, "uuid": process_doc.get("id") if process_doc else None} if process_slug else None
        ),
        "thread": {"slug": thread_slug, "uuid": thread_doc.get("id") if thread_doc else None} if thread_slug else None,
        "apt_id": env_data.get("apt_id"),
        "terminal": (
            {"id": env_data.get("terminal_id"), "provider": env_data.get("provider")}
            if env_data.get("terminal_id") or env_data.get("provider")
            else None
        ),
        "roles": roles_info["roles"],
        "policies": roles_info["policies"],
        "sources": [],
    }

    expected_thread_identifier = None
    if process_slug and thread_slug:
        expected_thread_identifier = f"{process_slug}/{thread_slug}"

    resolver_context = _resolver_context(env_data, thread_doc, expected_thread_identifier)
    expected_thread_uuid = thread_doc.get("id") if isinstance(thread_doc, dict) else None
    expected_thread_ids = {
        value for value in (expected_thread_identifier, expected_thread_uuid) if isinstance(value, str) and value
    }

    candidate_session_ids: List[str] = []
    provider_session = env_data.get("provider_session")
    if provider_session:
        candidate_session_ids.append(provider_session)

    if thread_doc:
        session_id = thread_doc.get("session_id")
        if session_id:
            candidate_session_ids.append(str(session_id))
        metadata = thread_doc.get("metadata")
        if isinstance(metadata, dict):
            meta_session = metadata.get("provider_session_id")
            if meta_session:
                candidate_session_ids.append(str(meta_session))

    candidate_session_ids = list(dict.fromkeys(filter(None, candidate_session_ids)))

    receipts: List[dict] = []
    for session_id in candidate_session_ids:
        receipt = _session_receipt(session_id)
        if receipt:
            receipts.append(receipt)
        else:
            warnings_list.append(f"Session receipt '{session_id}' not found under {_aware_home() / 'sessions'}.")

    if not receipts:
        resolver_thread = resolver_context.get("thread_identifier")
        resolver_provider = resolver_context.get("provider")
        if resolver_thread and resolver_provider:
            discovery = _discover_session_via_runtime(
                resolver_thread,
                resolver_provider,
                terminal_id=resolver_context.get("terminal_id"),
                apt_id=resolver_context.get("apt_id"),
            )
            if discovery.get("success"):
                sources.append("terminal-resolver")
                discovery_data = discovery.get("data") or {}
                terminal_payload = payload.get("terminal") or {}
                terminal_payload.setdefault("provider", resolver_provider)
                if discovery_data.get("provider"):
                    terminal_payload["provider"] = discovery_data["provider"]
                session_id = discovery_data.get("session_id")
                if session_id:
                    receipt = _session_receipt(str(session_id))
                    if receipt:
                        receipts.append(receipt)
                    terminal_payload.setdefault("session_id", str(session_id))
                if discovery_data.get("terminal_id"):
                    terminal_payload.setdefault("id", discovery_data.get("terminal_id"))
                payload["terminal"] = terminal_payload
                for entry in _all_session_receipts():
                    if entry.get("thread_id") == resolver_thread and entry not in receipts:
                        receipts.append(entry)
            else:
                message = discovery.get("message")
                if message:
                    warnings_list.append(f"Provider session discovery failed: {message}")

    if not receipts:
        all_receipts = _all_session_receipts()
        apt_id = resolver_context.get("apt_id") or env_data.get("apt_id")
        for entry in all_receipts:
            if apt_id and entry.get("apt_id") == apt_id:
                receipts.append(entry)
            elif expected_thread_ids and entry.get("thread_id") in expected_thread_ids:
                receipts.append(entry)
        if not receipts and all_receipts:
            receipts.extend(all_receipts)

    receipts = list({entry.get("session_id"): entry for entry in receipts if entry.get("session_id")}.values())

    if receipts:
        if expected_thread_ids:
            preferred = [
                entry for entry in receipts if entry.get("thread_id") in expected_thread_ids
            ]
            others = [entry for entry in receipts if entry not in preferred]

            def _sort_key(item: dict) -> str:
                return item.get("updated_at") or item.get("created_at") or ""

            preferred.sort(key=_sort_key, reverse=True)
            others.sort(key=_sort_key, reverse=True)
            receipts = preferred + others

        extra_sources = _merge_session_receipts(
            payload,
            receipts,
            env_data,
            expected_thread_identifier,
            expected_thread_uuid,
            warnings_list,
        )
        if extra_sources:
            sources.extend(extra_sources)

    payload["sources"] = sorted(set(filter(None, sources)))

    if warnings_list:
        payload["warnings"] = warnings_list

    return {key: value for key, value in payload.items() if value}


def list_agents(identities_root: Path | str | None = None) -> List[dict]:
    root = _resolve_identities_root(identities_root)
    agents_dir = root / "agents"
    if not agents_dir.exists():
        return []

    entries: List[dict] = []
    for agent_dir in sorted(path for path in agents_dir.iterdir() if path.is_dir()):
        agent_file = agent_dir / "agent.json"
        agent_id = None
        agent_name = agent_dir.name
        if agent_file.exists():
            data = _read_json(agent_file)
            if data:
                agent_id = data.get("id")
                identity = data.get("identity")
                if isinstance(identity, dict):
                    agent_name = identity.get("public_key") or agent_name
        processes_dir = agent_dir / "runtime" / "process"
        processes: List[str] = []
        if processes_dir.exists():
            processes = sorted(p.name for p in processes_dir.iterdir() if p.is_dir())

        canonical_id = agent_id or agent_dir.name
        entries.append(
            {
                "id": canonical_id,
                "uuid": agent_id,
                "slug": agent_dir.name,
                "agent_id": agent_id,
                "handle": agent_dir.name,
                "name": agent_name,
                "path": str(agent_dir.relative_to(root)),
                "processes": processes,
            }
        )
    return entries


def whoami(
    identities_root: Path | str | None,
    *,
    agent: Optional[str] = None,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    receipt_file: Optional[str] = None,
) -> dict:
    root = _resolve_identities_root(identities_root)
    payload = _build_whoami_payload(root, agent=agent, process=process, thread=thread)
    _write_receipt(receipt_file, payload)
    return payload


__all__ = ["list_agents", "whoami", "_resolve_identities_root"]
