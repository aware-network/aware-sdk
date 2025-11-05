"""Shared session utilities for agent thread workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from aware_environment.fs import apply_plan

from .._shared.fs_utils import _safe_load_json
from .write_plan import plan_session_update
from aware_environments.kernel._shared.receipts import receipt_to_dict, receipt_to_journal_entry


def _iso_now() -> str:
    """Return current UTC time in ISO-8601 format without microseconds."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _agent_thread_metadata_path(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
) -> Path:
    """Compute the path to an agent thread metadata document."""
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


def session_update(
    identities_root: Path,
    *,
    agent: str,
    process: str,
    thread: str,
    session_id: Optional[str] = None,
    provider: Optional[str] = None,
    terminal_id: Optional[str] = None,
    metadata_updates: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update agent thread metadata (session + provider info).

    Parameters mirror the CLI handler but require explicit selector values and
    a pre-parsed metadata_updates dict.
    """

    metadata_path = _agent_thread_metadata_path(
        identities_root,
        agent=agent,
        process=process,
        thread=thread,
    )
    if not metadata_path.exists():
        raise FileNotFoundError(f"Agent thread metadata not found at {metadata_path}")

    data = _safe_load_json(metadata_path)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid metadata document at {metadata_path}")

    if session_id is not None:
        data["session_id"] = session_id

    metadata_block = data.get("metadata")
    if not isinstance(metadata_block, dict):
        metadata_block = {}

    if provider is not None:
        metadata_block["terminal_provider"] = provider
    if terminal_id is not None:
        metadata_block["terminal_id"] = terminal_id

    for key, value in (metadata_updates or {}).items():
        metadata_block[key] = value

    data["metadata"] = metadata_block
    data["updated_at"] = _iso_now()

    plan_bundle = plan_session_update(
        identities_root,
        agent=agent,
        process=process,
        thread=thread,
        payload=data,
    )
    receipt = apply_plan(plan_bundle.plan)
    receipt_dict = receipt_to_dict(receipt)

    return {
        "path": str(plan_bundle.result.path),
        "session_id": plan_bundle.result.session_id,
        "metadata": dict(plan_bundle.result.metadata),
        "receipts": [receipt_dict],
        "journal": [receipt_to_journal_entry(receipt_dict)],
    }


__all__ = ["session_update", "_agent_thread_metadata_path", "_iso_now"]
