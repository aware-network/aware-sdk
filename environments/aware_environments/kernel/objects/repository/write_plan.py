"""OperationPlan builders for repository index management."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from aware_environment.fs import (
    EnsureInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)

from .fs import RepositoryFSAdapter
from .models import RepositoryIndexEntry


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialise_entries(entries: Sequence[RepositoryIndexEntry]) -> str:
    payload = [entry.json_dict() for entry in entries]
    return json.dumps(payload, indent=2) + "\n"


@dataclass(frozen=True)
class RepositoryIndexPlanResult:
    """Result bundle wrapping the repository index operation plan."""

    plan: OperationPlan
    index_path: Path
    entries: tuple[RepositoryIndexEntry, ...]

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    def payload(self) -> dict[str, object]:
        return {
            "path": str(self.index_path),
            "entry_count": self.entry_count,
            "entries": [entry.json_dict() for entry in self.entries],
        }


def plan_repository_index_refresh(
    repository_root: Path,
    *,
    additional_paths: Iterable[Path] | None = None,
    include_stats: bool = True,
) -> RepositoryIndexPlanResult:
    """Produce an operation plan that refreshes the repository index JSON."""

    resolved_root = Path(repository_root).resolve()
    adapter = RepositoryFSAdapter(resolved_root)
    entries = tuple(
        adapter.build_index(
            include_stats=include_stats,
            additional_paths=additional_paths,
        )
    )
    content = _serialise_entries(entries)

    index_path = adapter.index_path
    timestamp = _now()
    event = "created" if not index_path.exists() else "modified"

    context = OperationContext(
        object_type="repository",
        function="index-refresh",
        selectors={"repository": str(resolved_root)},
    )

    plan = OperationPlan(
        context=context,
        ensure_dirs=(EnsureInstruction(path=index_path.parent),),
        writes=(
            WriteInstruction(
                path=index_path,
                content=content,
                policy=OperationWritePolicy.MODIFIABLE,
                event=event,
                doc_type="repository-index",
                timestamp=timestamp,
                metadata={
                    "repository": str(resolved_root),
                    "entry_count": len(entries),
                },
            ),
        ),
    )

    return RepositoryIndexPlanResult(plan=plan, index_path=index_path, entries=entries)


__all__ = ["RepositoryIndexPlanResult", "plan_repository_index_refresh"]
