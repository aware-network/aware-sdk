"""Shared utilities for project task scaffolding."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

TASK_DIR_TEMPLATE = {
    "analysis": "analysis",
    "design": "design",
    "implementation_changes": "implementation/changes",
    "backlog": "backlog",
    "features": "features",
    "assets": "assets",
}


def _task_bucket(status: str) -> str:
    status = status.lower()
    if status == "queued":
        return "_pending"
    if status in {"completed", "done"} or status.startswith("finished_"):
        return "_completed"
    return ""


def _task_directory(project_path: Path, task_slug: str, status: str) -> Path:
    bucket = _task_bucket(status)
    if bucket == "_pending":
        return project_path / "tasks" / "_pending" / task_slug
    if bucket == "_completed":
        return project_path / "tasks" / "_completed" / task_slug
    return project_path / "tasks" / task_slug


def _default_task_overview(title: str, status: str, author: Dict[str, str]) -> str:
    display_status = status.replace("_", " ").replace("-", " ").title()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        f"# {title}\n\n"
        "## Purpose\n"
        "- Pending kickoff. Update after initial analysis.\n\n"
        "## Current Status\n"
        f"- {display_status}\n\n"
        "## Next Steps\n"
        "- [ ] Record analysis findings.\n"
        "- [ ] Capture initial design outline.\n\n"
        "## Ownership\n"
        f"- Created: {today}\n"
        f"- Author Agent: {author.get('agent','unknown')}\n"
        f"- Author Process: {author.get('process','unknown')}\n"
        f"- Author Thread: {author.get('thread','unknown')}\n"
    )


def _normalize_status(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if normalized not in {"queued", "running"}:
        raise ValueError(f"Unsupported task status '{value}'. Expected queued or running.")
    return normalized


def _normalize_priority(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"low", "medium", "high", "critical"}:
        raise ValueError(f"Unsupported task priority '{value}'.")
    return normalized


__all__ = [
    "TASK_DIR_TEMPLATE",
    "_task_bucket",
    "_task_directory",
    "_default_task_overview",
    "_normalize_priority",
    "_normalize_status",
]
