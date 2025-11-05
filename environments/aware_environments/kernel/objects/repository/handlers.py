"""Kernel repository handlers exposed via object specs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .fs import RepositoryFSAdapter
from .write_plan import RepositoryIndexPlanResult, plan_repository_index_refresh


def _coerce_repository_root(repository_root: Path | str | None) -> Path:
    if repository_root is None:
        return Path(".").resolve()
    return Path(repository_root).expanduser().resolve()


def list_repositories(repository_root: Path | str | None = None) -> List[dict]:
    root = _coerce_repository_root(repository_root)
    adapter = RepositoryFSAdapter(root)
    entries = adapter.read_index()
    return [entry.json_dict() for entry in entries]


def repository_index_refresh(
    repository_root: Path | str,
    *,
    additional_paths: Optional[Iterable[str]] = None,
    include_stats: bool = True,
) -> RepositoryIndexPlanResult:
    root = _coerce_repository_root(repository_root)
    extra_paths: Sequence[Path] | None = None
    if additional_paths:
        extra_paths = tuple(Path(candidate).expanduser().resolve() for candidate in additional_paths)
    return plan_repository_index_refresh(root, additional_paths=extra_paths, include_stats=include_stats)


def repository_status(repository_root: Path | str) -> dict:
    root = _coerce_repository_root(repository_root)
    adapter = RepositoryFSAdapter(root)
    entries = adapter.read_index()
    if not entries:
        return {
            "workspace_root": str(root),
            "index_path": str(adapter.index_path),
            "entries": [],
        }
    resolved_root = root
    for entry in entries:
        if Path(entry.workspace_root).resolve() == resolved_root:
            selected = entry
            break
    else:
        selected = entries[0]
    payload = selected.json_dict()
    payload["index_path"] = str(adapter.index_path)
    return payload


__all__ = [
    "RepositoryIndexPlanResult",
    "list_repositories",
    "repository_index_refresh",
    "repository_status",
]
