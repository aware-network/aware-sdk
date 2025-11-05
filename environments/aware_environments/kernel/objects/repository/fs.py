"""Filesystem adapter for repository index management."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Iterable, List, Optional

from .models import RepositoryIndex, RepositoryIndexEntry, RepositoryStats

_IGNORE_DIRECTORIES = {".git", ".aware", "node_modules", "__pycache__"}


class RepositoryFSAdapter:
    """Builds and reads the repository index."""

    def __init__(self, repo_root: Path | str | None = None) -> None:
        self.repo_root = Path(repo_root or Path.cwd()).resolve()
        self.index_path = self.repo_root / ".aware" / "index" / "repository_index.json"

    def read_index(self) -> List[RepositoryIndexEntry]:
        if not self.index_path.exists():
            return []
        try:
            raw_entries = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):  # pragma: no cover - defensive
            return []
        try:
            return RepositoryIndex.model_validate(raw_entries).root
        except Exception:  # pragma: no cover - defensive
            return []

    def build_index(
        self,
        *,
        root: Optional[Path] = None,
        include_stats: bool = True,
        additional_paths: Iterable[Path] | None = None,
    ) -> List[RepositoryIndexEntry]:
        primary_root = Path(root or self.repo_root).resolve()
        paths = {primary_root}
        for extra in additional_paths or []:
            paths.add(extra.resolve())

        entries: List[RepositoryIndexEntry] = []
        for repo_path in sorted(paths):
            entry = self._index_repository(repo_path, include_stats=include_stats)
            entries.append(entry)
        return entries

    def write_index(self, entries: List[RepositoryIndexEntry]) -> Path:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.index_path.with_suffix(".tmp")
        payload = [entry.json_dict() for entry in entries]
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(self.index_path)
        return self.index_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _index_repository(self, repo_path: Path, *, include_stats: bool) -> RepositoryIndexEntry:
        repo_path = repo_path.resolve()
        repository_id = sha256(str(repo_path).encode("utf-8")).hexdigest()
        name = repo_path.name or repo_path.as_posix()

        file_count = directory_count = approx_size_bytes = None
        if include_stats:
            file_count, directory_count, approx_size_bytes = self._gather_stats(repo_path)

        stats = None
        if include_stats:
            stats = RepositoryStats(
                file_count=file_count,
                directory_count=directory_count,
                approx_size_bytes=approx_size_bytes,
            )

        return RepositoryIndexEntry(
            repository_id=repository_id,
            workspace_root=str(repo_path),
            name=name,
            project_slug=None,
            default_expanded_paths=self._default_expanded_paths(repo_path),
            stats=stats,
            metadata={"commit_modes": ["filesystem"]},
            updated_at=datetime.now(timezone.utc),
        )

    def _default_expanded_paths(self, repo_root: Path) -> List[str]:
        paths: List[str] = []
        for child in repo_root.iterdir():
            if child.is_dir() and child.name not in _IGNORE_DIRECTORIES:
                paths.append(child.name)
        return sorted(paths)

    def _gather_stats(self, repo_root: Path) -> tuple[int, int, int]:
        file_count = 0
        directory_count = 0
        total_size = 0

        for root, dirnames, filenames in os.walk(repo_root):
            path = Path(root)
            dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRECTORIES]
            directory_count += len(dirnames)
            for filename in filenames:
                file_path = path / filename
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    continue
                file_count += 1
        return file_count, directory_count, total_size


__all__ = ["RepositoryFSAdapter"]
