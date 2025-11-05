"""Kernel handlers for agent-thread-memory object."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from .._shared.timeline import ensure_aware_datetime
from aware_environments.kernel._shared.receipts import receipt_to_dict, receipt_to_journal_entry
from aware_environment.fs import apply_plan
from .adapter import AgentThreadFSAdapter
from .models import EpisodicEntry, MemorySummary, WorkingMemoryAuthor, WorkingMemoryDocument
from .write_plan import plan_write_working_memory, plan_append_episodic_entry


_MEMORY_RULE_IDS = ("04-agent-01-memory-hierarchy",)


def memory_status(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    limit: int = 5,
) -> dict:
    adapter = AgentThreadFSAdapter(identities_root)
    summary: MemorySummary = adapter.list_summary(agent=agent, process=process, thread=thread, limit=limit)
    payload = summary.model_dump(mode="json")
    payload.setdefault("rule_ids", _MEMORY_RULE_IDS)
    return payload


def memory_history(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    limit: int = 20,
    significance: Optional[str] = None,
    session_type: Optional[str] = None,
) -> list[dict]:
    adapter = AgentThreadFSAdapter(identities_root)
    summary = adapter.list_summary(
        agent=agent,
        process=process,
        thread=thread,
        limit=limit,
        significance=significance,
        session_type=session_type,
    )
    entries = [entry.model_dump(mode="json") for entry in summary.episodic]
    return {"entries": entries, "rule_ids": _MEMORY_RULE_IDS}


def memory_write_working(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    content: str,
    author_agent: Optional[str] = None,
    author_process: Optional[str] = None,
    author_thread: Optional[str] = None,
) -> dict:
    author = WorkingMemoryAuthor(
        agent=author_agent or agent,
        process=author_process or process,
        thread=author_thread or thread,
    )
    plan_result = plan_write_working_memory(
        identities_root,
        agent=agent,
        process=process,
        thread=thread,
        author=author,
        content=content,
    )
    receipt = apply_plan(plan_result.plan)
    receipt_dict = receipt_to_dict(receipt)
    document = plan_result.document.model_dump(mode="json")
    return {
        **document,
        "receipts": [receipt_dict],
        "journal": [receipt_to_journal_entry(receipt_dict)],
    }


def memory_append_episodic(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    title: str,
    content: str,
    author_agent: Optional[str] = None,
    author_process: Optional[str] = None,
    author_thread: Optional[str] = None,
    session_type: Optional[str] = None,
    significance: Optional[str] = None,
) -> dict:
    author = WorkingMemoryAuthor(
        agent=author_agent or agent,
        process=author_process or process,
        thread=author_thread or thread,
    )
    plan_result = plan_append_episodic_entry(
        identities_root,
        agent=agent,
        process=process,
        thread=thread,
        title=title,
        content=content,
        session_type=session_type,
        significance=significance,
        author=author,
    )
    receipt = apply_plan(plan_result.plan)
    receipt_dict = receipt_to_dict(receipt)
    entry = plan_result.entry.model_dump(mode="json")
    return {
        **entry,
        "receipts": [receipt_dict],
        "journal": [receipt_to_journal_entry(receipt_dict)],
    }


def memory_diff(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    since: str | datetime,
) -> list[dict]:
    if isinstance(since, str):
        parsed = ensure_aware_datetime(since)
        if parsed is None:
            raise ValueError("Invalid since timestamp")
        since_dt = parsed
    else:
        since_dt = since
    adapter = AgentThreadFSAdapter(identities_root)
    events = adapter.diff_since(agent=agent, process=process, thread=thread, since=since_dt)
    return {"events": events, "rule_ids": _MEMORY_RULE_IDS}


def memory_validate(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
) -> dict:
    adapter = AgentThreadFSAdapter(identities_root)
    payload = adapter.validate(agent=agent, process=process, thread=thread)
    if isinstance(payload, dict):
        payload = dict(payload)
        payload.setdefault("rule_ids", _MEMORY_RULE_IDS)
        return payload
    return {"result": payload, "rule_ids": _MEMORY_RULE_IDS}


__all__ = [
    "memory_status",
    "memory_history",
    "memory_write_working",
    "memory_append_episodic",
    "memory_diff",
    "memory_validate",
]
