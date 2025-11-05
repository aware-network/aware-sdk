"""OperationPlan builders for agent-thread memory writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import yaml
from aware_environment.fs import (
    EnsureInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)
from .._shared.frontmatter import load_frontmatter
from .._shared.timeline import ensure_aware_datetime
from .models import EpisodicEntry, EpisodicEntryHeader, WorkingMemoryAuthor, WorkingMemoryDocument


def _isoformat(dt: datetime) -> str:
    aware = dt.astimezone(timezone.utc)
    trimmed = aware.replace(microsecond=0)
    return trimmed.isoformat().replace("+00:00", "Z")


def _iso_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class WorkingMemoryPlanResult:
    plan: OperationPlan
    document: WorkingMemoryDocument


@dataclass(frozen=True)
class EpisodicEntryPlanResult:
    plan: OperationPlan
    entry: EpisodicEntry


def plan_write_working_memory(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    author: WorkingMemoryAuthor,
    content: str,
) -> WorkingMemoryPlanResult:
    thread_root = (
        Path(identities_root)
        / "agents"
        / agent
        / "runtime"
        / "process"
        / process
        / "threads"
        / thread
    )
    working_path = thread_root / "working_memory.md"

    existing = load_frontmatter(working_path) if working_path.exists() else None
    metadata: Dict[str, object] = dict(existing.metadata) if existing else {}
    now = _iso_now()
    updated_stamp = _isoformat(now)

    metadata.update(
        {
            "id": metadata.get("id") or f"working-memory-{thread}-{process}",
            "author": author.model_dump(mode="json"),
            "updated": updated_stamp,
        }
    )
    metadata.setdefault("created", updated_stamp)

    header_text = yaml.safe_dump(metadata, sort_keys=False).strip()
    body = content.rstrip() + "\n" if content.strip() else ""
    text = f"---\n{header_text}\n---\n\n{body}" if body else f"---\n{header_text}\n---\n"

    selectors = {
        "agent": agent,
        "process": process,
        "thread": thread,
    }
    context = OperationContext(object_type="agent-thread-memory", function="write-working", selectors=selectors)

    plan = OperationPlan(
        context=context,
        ensure_dirs=(EnsureInstruction(path=working_path.parent),),
        writes=(
            WriteInstruction(
                path=working_path,
                content=text,
                policy=OperationWritePolicy.MODIFIABLE,
                event="modified",
                doc_type="working-memory",
                timestamp=now,
                metadata={"agent": agent, "process": process, "thread": thread},
            ),
        ),
    )

    created_value = metadata.get("created")
    created_dt = ensure_aware_datetime(created_value) if created_value else None

    document = WorkingMemoryDocument(
        id=metadata["id"],
        author=author,
        updated=now,
        created=created_dt,
        content=content,
        path=str(working_path.relative_to(identities_root)),
    )

    return WorkingMemoryPlanResult(plan=plan, document=document)


def plan_append_episodic_entry(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    author: WorkingMemoryAuthor,
    title: str,
    content: str,
    session_type: Optional[str],
    significance: Optional[str],
) -> EpisodicEntryPlanResult:
    thread_root = (
        Path(identities_root)
        / "agents"
        / agent
        / "runtime"
        / "process"
        / process
        / "threads"
        / thread
    )
    episodic_dir = thread_root / "episodic"
    now = _iso_now()
    timestamp_slug = now.strftime("%Y-%m-%d-%H-%M-%S")
    safe_title = title.strip().lower().replace(" ", "-") or "entry"
    filename = f"{timestamp_slug}-{safe_title}.md"
    path = episodic_dir / filename

    metadata: Dict[str, object] = {
        "id": f"episodic-{thread}-{timestamp_slug}-{safe_title}",
        "author": author.model_dump(mode="json"),
        "timestamp": _isoformat(now),
    }
    if session_type:
        metadata["session_type"] = session_type
    if significance:
        metadata["significance"] = significance
    header_text = yaml.safe_dump(metadata, sort_keys=False).strip()
    body_text = content.rstrip() + "\n"
    text = f"---\n{header_text}\n---\n\n{body_text}"

    selectors = {
        "agent": agent,
        "process": process,
        "thread": thread,
    }
    context = OperationContext(object_type="agent-thread-memory", function="append-episodic", selectors=selectors)

    plan = OperationPlan(
        context=context,
        ensure_dirs=(EnsureInstruction(path=episodic_dir),),
        writes=(
            WriteInstruction(
                path=path,
                content=text,
                policy=OperationWritePolicy.WRITE_ONCE,
                event="created",
                doc_type="episodic-entry",
                timestamp=now,
                metadata={"agent": agent, "process": process, "thread": thread},
            ),
        ),
    )

    header = EpisodicEntryHeader(
        id=metadata["id"],
        author=author,
        timestamp=now,
        session_type=session_type,
        significance=significance,
    )
    entry = EpisodicEntry(
        header=header,
        body=content,
        path=str(path.relative_to(identities_root)),
    )

    return EpisodicEntryPlanResult(plan=plan, entry=entry)


__all__ = [
    "WorkingMemoryPlanResult",
    "EpisodicEntryPlanResult",
    "plan_write_working_memory",
    "plan_append_episodic_entry",
]
