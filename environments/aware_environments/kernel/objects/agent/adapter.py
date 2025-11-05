"""Filesystem helpers for agent/process/thread scaffolding."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Mapping
from uuid import UUID, uuid4

from aware_environment.fs import apply_plan
from ..agent_thread_memory import (
    memory_write_working,
    WorkingMemoryAuthor,
)


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_json(path: Path, payload: dict) -> None:
    _ensure_directory(path.parent)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ProcessCreationResult:
    process_path: Path
    payload: dict
    status: str


@dataclass(frozen=True)
class ThreadCreationResult:
    hierarchy: dict
    thread_path: Path
    payload: dict


def create_process(
    identities_root: Path,
    *,
    agent_slug: str,
    process_slug: str,
    display_name: Optional[str] = None,
    force: bool = False,
) -> ProcessCreationResult:
    identities_root = Path(identities_root).resolve()
    agent_dir = identities_root / "agents" / agent_slug
    process_dir = agent_dir / "runtime" / "process" / process_slug
    _ensure_directory(process_dir)

    agent_data = _load_json(agent_dir / "agent.json") or {
        "id": str(uuid4()),
        "identity": {"public_key": agent_slug},
        "name": agent_slug,
    }
    _write_json(agent_dir / "agent.json", agent_data)

    process_file = process_dir / "process.json"
    if process_file.exists() and not force:
        payload = _load_json(process_file) or {}
        return ProcessCreationResult(process_path=process_file, payload=payload, status="exists")

    existing = _load_json(process_file) or {}
    process_uuid = existing.get("id") if existing and not force else str(uuid4())
    now = _now_iso()
    payload = {
        "id": process_uuid,
        "slug": process_slug,
        "agent_id": agent_data.get("id"),
        "name": display_name or existing.get("name") or process_slug,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    if display_name:
        payload["display_name"] = display_name

    _write_json(process_file, payload)
    _update_agent_process_manifest(agent_dir, process_slug, payload)
    return ProcessCreationResult(process_path=process_file, payload=payload, status="created")


def _update_agent_process_manifest(agent_dir: Path, process_slug: str, payload: dict) -> None:
    manifest_path = agent_dir / "runtime" / "process" / "agent_process.json"
    data = _load_json(manifest_path) or {
        "processes": [],
        "updated_at": _now_iso(),
    }
    processes = [entry for entry in data.get("processes", []) if entry.get("slug") != process_slug]
    processes.append(
        {
            "slug": process_slug,
            "id": payload.get("id"),
            "name": payload.get("name"),
        }
    )
    data["processes"] = processes
    data["updated_at"] = _now_iso()
    _write_json(manifest_path, data)


def create_thread(
    identities_root: Path,
    *,
    agent_slug: str,
    process_slug: str,
    thread_slug: str,
    is_main: bool = False,
    status: str = "running",
    execution_mode: str = "native",
    description: Optional[str] = None,
    actor_id: Optional[UUID] = None,
    thread_id: Optional[UUID] = None,
) -> ThreadCreationResult:
    identities_root = Path(identities_root).resolve()
    agent_dir = identities_root / "agents" / agent_slug
    process_dir = agent_dir / "runtime" / "process" / process_slug
    thread_dir = process_dir / "threads" / thread_slug

    if thread_dir.exists():
        raise FileExistsError(f"Thread '{agent_slug}/{process_slug}/{thread_slug}' already exists.")

    _ensure_directory(agent_dir)
    _ensure_directory(process_dir)
    _ensure_directory(thread_dir)

    agent_data = _load_json(agent_dir / "agent.json") or {
        "id": str(uuid4()),
        "identity": {"public_key": agent_slug},
        "name": agent_slug,
    }
    _write_json(agent_dir / "agent.json", agent_data)

    process_path = process_dir / "agent_process.json"
    process_data = _load_json(process_path) or {
        "id": str(uuid4()),
        "agent_id": agent_data.get("id"),
        "name": process_slug,
        "status": "running",
        "created_at": _now_iso(),
    }
    process_data["updated_at"] = _now_iso()
    _write_json(process_path, process_data)

    thread_uuid = thread_id or uuid4()
    actor_uuid = actor_id or uuid4()
    now_iso = _now_iso()
    memory_working_id = uuid4()
    memory_episodic_id = uuid4()
    system_instruction_id = uuid4()

    thread_payload = {
        "id": str(thread_uuid),
        "agent_process_id": process_data.get("id"),
        "actor_id": str(actor_uuid),
        "memory_working_id": str(memory_working_id),
        "memory_episodic_id": str(memory_episodic_id),
        "system_instruction_id": str(system_instruction_id),
        "active_session_permit_id": None,
        "active_inference_model_id": None,
        "is_main": is_main,
        "execution_mode": execution_mode,
        "iteration_count": 0,
        "tool_retry_count": 0,
        "name": thread_slug,
        "active_permit_nonce": None,
        "session_id": None,
        "needs_rebootstrap": False,
        "session_bootstrapped_at": None,
        "active_permit_expires_at": None,
        "status": status,
        "created_at": now_iso,
        "updated_at": now_iso,
        "agent_process_thread_inference_model_list": [],
        "agent_process_thread_tool_list": [],
        "agent_process_thread_iteration_list": [],
    }
    if description:
        thread_payload["description"] = description

    thread_path = thread_dir / "agent_process_thread.json"
    _write_json(thread_path, thread_payload)
    _ensure_directory(thread_dir / "episodic")

    # Seed working memory content
    author = WorkingMemoryAuthor(agent=agent_slug, process=process_slug, thread=thread_slug)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    default_memory_content = (
        f"# Working Memory: {agent_slug}\n"
        f"## Thread: {thread_slug} | Process: {process_slug} | Agent: {agent_slug}\n\n"
        "## Active Session Context\n"
        f"- **Agent**: {agent_slug}\n"
        f"- **Process**: {process_slug}\n"
        f"- **Thread**: {thread_slug}\n"
        f"- **Date**: {today}\n"
        "- **Autonomy Level**: 3 (Initialized via CLI scaffold)\n\n"
        "## Current Task: Pending Initialization\n"
        "**Project**: TBD\n"
        "**Task**: TBD\n"
        "**Status**: RUNNING\n"
        "**Priority**: MEDIUM\n\n"
        "## Active Working Items\n"
        "- Placeholder – update after establishing session context.\n\n"
        "## Key Technical Context (Active)\n"
        "- Pending updates.\n\n"
        "## Architecture Decisions Made\n"
        "- None recorded yet.\n\n"
        "## Immediate Next Actions\n"
        "1. Populate working memory with real context.\n"
        "2. Record an episodic entry after first coordination touchpoint.\n\n"
        "## Memory Integration Points\n"
        "- **Semantic**: Pending\n"
        "- **Procedural**: Pending\n"
        "- **Episodic**: Pending\n"
        "- **Working**: Initial scaffold captured by CLI.\n\n"
        "## Session Notes\n"
        "- Kernel scaffold created thread resources; update with live context.\n"
    )
    working_payload = memory_write_working(
        identities_root,
        agent=agent_slug,
        process=process_slug,
        thread=thread_slug,
        content=default_memory_content,
        author_agent=author.agent,
        author_process=author.process,
        author_thread=author.thread,
    )
    if isinstance(working_payload, Mapping):
        pass
    else:  # pragma: no cover - legacy fallback when kernel returns plan result
        apply_plan(working_payload.plan)

    hierarchy = {
        "agent_data": agent_data,
        "process_data": process_data,
        "thread_data": thread_payload,
    }

    return ThreadCreationResult(hierarchy=hierarchy, thread_path=thread_dir, payload=thread_payload)


__all__ = [
    "create_process",
    "create_thread",
    "ProcessCreationResult",
    "ThreadCreationResult",
]
