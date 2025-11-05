"""OperationPlan builders for agent-thread metadata writes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

from aware_environment.fs import (
    EnsureInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)


def _iso_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SessionUpdateResult:
    path: Path
    session_id: Optional[str]
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class SessionUpdatePlan:
    plan: OperationPlan
    result: SessionUpdateResult


def _metadata_path(identities_root: Path, agent: str, process: str, thread: str) -> Path:
    return (
        Path(identities_root)
        / "agents"
        / agent
        / "runtime"
        / "process"
        / process
        / "threads"
        / thread
        / "agent_process_thread.json"
    )


def _selectors(agent: str, process: str, thread: str) -> Mapping[str, str]:
    return {
        "agent": agent,
        "process": process,
        "thread": thread,
    }


def plan_session_update(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    payload: Mapping[str, object],
) -> SessionUpdatePlan:
    metadata_path = _metadata_path(identities_root, agent, process, thread)
    timestamp = _iso_now()
    context = OperationContext(
        object_type="agent-thread",
        function="session-update",
        selectors=_selectors(agent, process, thread),
    )

    content = json.dumps(payload, indent=2) + "\n"
    metadata_block = payload.get("metadata")
    metadata_summary = {}
    if isinstance(metadata_block, Mapping):
        metadata_summary = {str(key): str(value) for key, value in metadata_block.items()}

    write_instruction = WriteInstruction(
        path=metadata_path,
        content=content,
        policy=OperationWritePolicy.MODIFIABLE,
        event="modified",
        doc_type="agent-thread-metadata",
        timestamp=timestamp,
        metadata={"session_id": payload.get("session_id"), "metadata": metadata_summary},
    )

    plan = OperationPlan(
        context=context,
        ensure_dirs=(EnsureInstruction(path=metadata_path.parent),),
        writes=(write_instruction,),
    )

    result = SessionUpdateResult(
        path=metadata_path,
        session_id=str(payload.get("session_id")) if payload.get("session_id") else None,
        metadata=metadata_summary,
    )

    return SessionUpdatePlan(plan=plan, result=result)


__all__ = ["SessionUpdatePlan", "SessionUpdateResult", "plan_session_update"]

