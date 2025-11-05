"""Callable handlers exposed via agent object specs."""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, List, Dict, Sequence

from aware_environment import Environment
from aware_environment.renderer import render_agent_document, render_role_bundle

from .adapter import (
    ProcessCreationResult,
    create_process,
    create_thread,
)
from .helpers import list_agents as _list_agents_helper, whoami as _whoami_helper, _resolve_identities_root, _aware_home
from ..role.handlers import list_roles as _list_roles
from ..agent_thread.handlers import login as _agent_thread_login

DEFAULT_ROLE_SLUGS: Sequence[str] = ("memory-baseline", "project-task-baseline")
_ENVIRONMENT_CACHE: Environment | None = None


def _environment() -> Environment:
    global _ENVIRONMENT_CACHE
    if _ENVIRONMENT_CACHE is None:
        from ...registry import get_environment  # local import to avoid circular dependency
        _ENVIRONMENT_CACHE = get_environment()
    return _ENVIRONMENT_CACHE


def _normalize_alias(value: str) -> str:
    normalized = value.replace("/", "-").replace("_", "-")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip().lower()


def _build_aliases(
    *,
    actor_id: str,
    agent_slug: str,
    process_slug: str,
    thread_slug: str,
) -> List[str]:
    aliases = {
        actor_id,
        _normalize_alias(f"{agent_slug}-{process_slug}-{thread_slug}"),
        _normalize_alias(f"{agent_slug}-{thread_slug}"),
        _normalize_alias(f"{agent_slug}-thread-{thread_slug}"),
        _normalize_alias(f"{thread_slug}-{agent_slug}-{process_slug}"),
    }
    aliases.discard("")
    return list(aliases)


def _update_actor_registry(
    *,
    identities_root: Path,
    actor_id: Optional[str],
    agent_id: Optional[str],
    agent_slug: str,
    agent_name: Optional[str],
    process_slug: str,
    thread_slug: str,
    thread_path: Path,
) -> None:
    if not actor_id:
        return
    registry_dir = identities_root / "_registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_path = registry_dir / "actor_registry.json"

    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            registry = {"generated_at": None, "actors": {}, "aliases": {}}
    else:
        registry = {"generated_at": None, "actors": {}, "aliases": {}}

    actors = registry.setdefault("actors", {})
    aliases_map = registry.setdefault("aliases", {})

    entry = {
        "id": actor_id,
        "type": "agentProcessThread",
        "identity_id": agent_id,
        "agent_id": agent_id,
        "agent_handle": agent_slug,
        "agent_name": agent_name or agent_slug,
        "process_name": process_slug,
        "thread_name": thread_slug,
        "path": str(thread_path.relative_to(identities_root)),
    }

    aliases = _build_aliases(
        actor_id=actor_id,
        agent_slug=agent_slug,
        process_slug=process_slug,
        thread_slug=thread_slug,
    )
    entry["aliases"] = aliases
    actors[actor_id] = entry

    for alias in aliases:
        existing = aliases_map.get(alias)
        if existing and existing != actor_id:
            continue
        aliases_map[alias] = actor_id

    registry["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


def _split_role_arguments(values: Optional[Iterable[str]]) -> List[str]:
    if not values:
        return []
    result: List[str] = []
    for value in values:
        if not value:
            continue
        for candidate in str(value).split(","):
            trimmed = candidate.strip()
            if trimmed:
                result.append(trimmed)
    return result


def _resolve_roles(identities_root: Path, slugs: Sequence[str]) -> List[Dict[str, object]]:
    registry_roles = _list_roles(identities_root)
    if not registry_roles:
        env_registry = os.getenv("AWARE_ROLE_REGISTRY_PATH")
        if env_registry:
            registry_roles = _list_roles(None, registry_path=Path(env_registry).expanduser())
    if not registry_roles:
        registry_roles = _list_roles(None)
    if not registry_roles:
        raise ValueError(
            "Role registry not found. Expected docs/identities/_registry/role_registry.json or AWARE_ROLE_REGISTRY_PATH."
        )
    lookup = {}
    for entry in registry_roles:
        slug = str(entry.get("slug")).strip().lower()
        if slug:
            lookup[slug] = entry
        role_id = entry.get("id")
        if isinstance(role_id, str) and role_id.strip():
            lookup.setdefault(role_id.strip().lower(), entry)

    resolved: List[Dict[str, object]] = []
    for slug in slugs:
        key = slug.strip().lower()
        role_entry = lookup.get(key)
        if role_entry is None:
            raise ValueError(f"Role '{slug}' not found. Update docs/identities/_registry/role_registry.json")
        resolved.append(role_entry)
    return resolved


def _build_roles_payload(
    *,
    agent_slug: str,
    agent_id: Optional[str],
    actor_id: Optional[str],
    process_slug: str,
    thread_slug: str,
    roles: Sequence[Dict[str, object]],
) -> Dict[str, object]:
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    role_entries: List[Dict[str, object]] = []
    for role in roles:
        entry = {
            "slug": role.get("slug"),
            "title": role.get("title"),
            "description": role.get("description"),
            "policies": list(role.get("policies", [])),
            "cli_objects": list(role.get("cli_objects", [])),
            "policy_details": list(role.get("policy_details", [])),
        }
        role_entries.append(entry)

    return {
        "generated_at": now_iso,
        "agent": agent_slug,
        "agent_id": agent_id,
        "actor_id": actor_id,
        "process": process_slug,
        "thread": thread_slug,
        "roles": role_entries,
    }


def _write_agent_guide(
    *,
    identities_root: Path,
    agent_slug: str,
    agent_id: Optional[str],
    agent_name: Optional[str],
    actor_id: Optional[str],
    process_slug: str,
    thread_slug: str,
    role_slugs: Sequence[str],
    guide_path: Path,
) -> None:
    environment = _environment()
    identity_label = agent_name or agent_id or agent_slug
    context_map = OrderedDict(
        (
            ("Agent ID", agent_id or "-"),
            ("Actor ID", actor_id or "-"),
            ("Process", process_slug),
            ("Thread", thread_slug),
        )
    )

    try:
        env_doc = render_agent_document(
            environment,
            agent_slug,
            identity=identity_label,
            context=context_map,
            heading_level=2,
        ).strip()
    except ValueError:
        try:
            role_section = render_role_bundle(environment, tuple(role_slugs)).strip()
        except ValueError:
            role_section = ""
        fallback_lines: List[str] = [
            f"## Agent · {agent_slug}",
            "",
            f"**Agent slug:** `{agent_slug}`",
        ]
        if identity_label:
            fallback_lines.append(f"**Identity:** `{identity_label}`")
        if context_map:
            fallback_lines.extend(["", "### Context", ""])
            for key, value in context_map.items():
                fallback_lines.append(f"- **{key}:** `{value}`")
        if role_section:
            fallback_lines.extend(["", "### Roles", "", role_section])
        fallback_lines.extend(
            [
                "",
                "### Capabilities",
                "",
                "| Function | Description |",
                "| --- | --- |",
                "| `signup` | Ensure agent identity scaffold. |",
                "| `create-process` | Ensure agent process metadata. |",
                "| `create-thread` | Provision agent thread scaffold. |",
                "| `whoami` | Inspect current bindings. |",
                "| `login` | Bind terminal provider session. |",
                "| `session-update` | Update thread session metadata. |",
            ]
        )
        env_doc = "\n".join(fallback_lines).strip()

    guide_lines = [
        f"# Agent Guide · {agent_slug}/{process_slug}/{thread_slug}",
        "",
        env_doc,
        "",
        "## Local Context",
        "",
        "- Working memory: ./working_memory.md",
        "- Episodic entries: ./episodic/",
        "- Role registry: ./roles.json",
    ]
    guide_path.write_text("\n".join(guide_lines).strip() + "\n", encoding="utf-8")


def _finalise_thread(
    *,
    identities_root: Path,
    agent_slug: str,
    process_slug: str,
    thread_slug: str,
    thread_status: str,
    thread_dir: Path,
    thread_payload: Dict[str, object],
    role_arguments: Optional[Iterable[str]],
) -> Dict[str, object]:
    identities_root = identities_root.resolve()
    agent_dir = identities_root / "agents" / agent_slug
    agent_file = agent_dir / "agent.json"
    agent_doc: Dict[str, object] = {}
    if agent_file.exists():
        try:
            agent_doc = json.loads(agent_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            agent_doc = {}

    agent_id = agent_doc.get("id") if isinstance(agent_doc, dict) else None
    identity_block = agent_doc.get("identity") if isinstance(agent_doc, dict) else None
    agent_name = None
    if isinstance(identity_block, dict):
        agent_name = identity_block.get("public_key") or identity_block.get("name")
    if not agent_name and isinstance(agent_doc, dict):
        agent_name = agent_doc.get("name")

    actor_id = thread_payload.get("actor_id") if isinstance(thread_payload, dict) else None

    role_values = _split_role_arguments(role_arguments)
    existing_roles = []
    if isinstance(thread_payload, dict):
        existing_roles = [
            str(value).strip()
            for value in thread_payload.get("roles", [])
            if str(value).strip()
        ]

    if role_values:
        candidate_roles = role_values
    elif existing_roles:
        candidate_roles = existing_roles
    else:
        candidate_roles = list(DEFAULT_ROLE_SLUGS)

    seen = set()
    role_slugs: List[str] = []
    for slug in candidate_roles:
        key = slug.strip()
        if not key:
            continue
        lower = key.lower()
        if lower in seen:
            continue
        seen.add(lower)
        role_slugs.append(key)

    resolved_roles = _resolve_roles(identities_root, role_slugs)
    roles_payload = _build_roles_payload(
        agent_slug=agent_slug,
        agent_id=str(agent_id) if agent_id else None,
        actor_id=str(actor_id) if isinstance(actor_id, str) else None,
        process_slug=process_slug,
        thread_slug=thread_slug,
        roles=resolved_roles,
    )

    roles_path = thread_dir / "roles.json"
    roles_path.write_text(json.dumps(roles_payload, indent=2) + "\n", encoding="utf-8")

    thread_json_path = thread_dir / "agent_process_thread.json"
    thread_doc: Dict[str, object] = {}
    if thread_json_path.exists():
        try:
            thread_doc = json.loads(thread_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            thread_doc = {}
    else:
        thread_doc = {}

    thread_doc["roles"] = role_slugs
    if thread_status and not thread_doc.get("status"):
        thread_doc["status"] = thread_status
    thread_json_path.write_text(json.dumps(thread_doc, indent=2) + "\n", encoding="utf-8")

    _update_actor_registry(
        identities_root=identities_root,
        actor_id=str(actor_id) if isinstance(actor_id, str) else None,
        agent_id=str(agent_id) if agent_id else None,
        agent_slug=agent_slug,
        agent_name=str(agent_name) if agent_name else None,
        process_slug=process_slug,
        thread_slug=thread_slug,
        thread_path=thread_dir,
    )

    guide_path = thread_dir / "AGENT.md"
    _write_agent_guide(
        identities_root=identities_root,
        agent_slug=agent_slug,
        agent_id=str(agent_id) if agent_id else None,
        agent_name=str(agent_name) if agent_name else None,
        actor_id=str(actor_id) if actor_id else None,
        process_slug=process_slug,
        thread_slug=thread_slug,
        role_slugs=role_slugs,
        guide_path=guide_path,
    )

    status_value = (
        thread_doc.get("status")
        if isinstance(thread_doc, dict) and thread_doc.get("status")
        else thread_payload.get("status")
    )

    return {
        "agent": agent_slug,
        "agent_id": agent_id,
        "process": process_slug,
        "thread": thread_slug,
        "thread_id": thread_payload.get("id"),
        "actor_id": actor_id,
        "path": str(thread_dir.relative_to(identities_root)),
        "status": status_value or thread_status,
        "execution_mode": thread_payload.get("execution_mode"),
        "is_main": thread_payload.get("is_main"),
        "roles": role_slugs,
        "roles_path": str(roles_path.relative_to(identities_root)),
        "guide_path": str(guide_path.relative_to(identities_root)),
    }


def _process_result_to_payload(result: ProcessCreationResult) -> dict:
    return {
        "status": result.status,
        "path": str(result.process_path),
        "data": result.payload,
    }


def create_process_handler(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    display_name: Optional[str] = None,
    force: bool = False,
) -> dict:
    result = create_process(
        identities_root,
        agent_slug=agent,
        process_slug=process,
        display_name=display_name,
        force=force,
    )
    return _process_result_to_payload(result)


def create_thread_handler(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    is_main: bool = False,
    status: str = "running",
    execution_mode: str = "native",
    description: Optional[str] = None,
    role: Optional[Iterable[str]] = None,
) -> dict:
    if not is_main and thread == "main":
        is_main = True

    identities_root = Path(identities_root).resolve()
    result = create_thread(
        identities_root,
        agent_slug=agent,
        process_slug=process,
        thread_slug=thread,
        is_main=is_main,
        status=status,
        execution_mode=execution_mode,
        description=description,
    )
    thread_payload = dict(result.payload)
    return _finalise_thread(
        identities_root=identities_root,
        agent_slug=agent,
        process_slug=process,
        thread_slug=thread,
        thread_status="created",
        thread_dir=result.thread_path,
        thread_payload=thread_payload,
        role_arguments=role,
    )


def signup_handler(
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
    terminal_shell: Optional[str] = None,  # retained for CLI compatibility
) -> dict:
    if not is_main and thread == "main":
        is_main = True

    identities_root = Path(identities_root).resolve()
    agent_dir = identities_root / "agents" / agent
    process_dir = agent_dir / "runtime" / "process" / process
    thread_dir = process_dir / "threads" / thread
    thread_json = thread_dir / "agent_process_thread.json"
    agent_file = agent_dir / "agent.json"
    agent_exists = agent_file.exists()

    process_result = create_process(
        identities_root,
        agent_slug=agent,
        process_slug=process,
        display_name=display_name,
        force=force,
    )

    thread_status = "created"
    thread_payload: Dict[str, object] = {}
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
        thread_payload = dict(thread_result.payload)
    except FileExistsError:
        thread_status = "exists"
        if thread_json.exists():
            try:
                thread_payload = json.loads(thread_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:  # pragma: no cover - malformed legacy data
                thread_payload = {}

    thread_summary = _finalise_thread(
        identities_root=identities_root,
        agent_slug=agent,
        process_slug=process,
        thread_slug=thread,
        thread_status=thread_status,
        thread_dir=thread_dir,
        thread_payload=thread_payload,
        role_arguments=None,
    )

    agent_status = "exists" if agent_exists else "created"

    terminal_payload: Optional[Dict[str, object]] = None
    terminal_id = with_terminal
    provider_slug = provider
    if terminal_id or provider_slug:
        thread_metadata: Dict[str, object] = {}
        if isinstance(thread_payload, dict):
            meta_value = thread_payload.get("metadata")
            if isinstance(meta_value, dict):
                thread_metadata = dict(meta_value)

        if provider_slug is None:
            candidate = thread_metadata.get("terminal_provider")
            if isinstance(candidate, str) and candidate:
                provider_slug = candidate
        if provider_slug is None:
            raise ValueError("Provider slug is required when ensuring terminal binding.")
        if not terminal_id:
            candidate_id = thread_metadata.get("terminal_id")
            if isinstance(candidate_id, str) and candidate_id:
                terminal_id = candidate_id
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

        terminal_payload = _agent_thread_login(
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

    payload: Dict[str, object] = {
        "agent": agent,
        "status": agent_status,
        "process": {
            "slug": process,
            "status": process_result.status,
            "path": str(process_result.process_path.relative_to(identities_root)),
        },
        "thread": {
            "slug": thread,
            "status": thread_status,
            "path": thread_summary["path"],
            "id": thread_summary.get("thread_id"),
        },
        "roles": thread_summary["roles"],
        "roles_path": thread_summary["roles_path"],
        "guide_path": thread_summary["guide_path"],
        "thread_id": thread_summary.get("thread_id"),
        "actor_id": thread_summary.get("actor_id"),
    }
    if terminal_payload is not None:
        payload["terminal"] = terminal_payload
    return payload


def list_agents(
    identities_root: Path | str | None = None,
) -> List[Dict[str, object]]:
    """Return discovered agent identities rooted under identities_root."""

    return _list_agents_helper(_resolve_identities_root(identities_root))


def whoami_handler(
    identities_root: Path | str | None = None,
    *,
    agent: Optional[str] = None,
    process: Optional[str] = None,
    thread: Optional[str] = None,
    receipt_file: Optional[str] = None,
) -> Dict[str, object]:
    """Inspect current agent/process/thread bindings, mirroring CLI whoami."""

    return _whoami_helper(
        _resolve_identities_root(identities_root),
        agent=agent,
        process=process,
        thread=thread,
        receipt_file=receipt_file,
    )


__all__ = [
    "list_agents",
    "whoami_handler",
    "create_process_handler",
    "create_thread_handler",
    "signup_handler",
]
