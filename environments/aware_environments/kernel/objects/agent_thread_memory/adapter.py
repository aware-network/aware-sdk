"""Filesystem adapter for agent thread working/episodic memory."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

import yaml

from .._shared.frontmatter import FrontmatterResult, load_frontmatter
from .._shared.timeline import ensure_aware_datetime
from .models import (
    EpisodicEntry,
    EpisodicEntryHeader,
    MemorySummary,
    WorkingMemoryAuthor,
    WorkingMemoryDocument,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentThreadFSAdapter:
    identities_root: Path

    def __post_init__(self) -> None:
        if not isinstance(self.identities_root, Path):
            self.identities_root = Path(str(self.identities_root))
        self.identities_root = self.identities_root.expanduser()

    def _thread_root(self, agent: str, process: str, thread: str) -> Path:
        return (
            self.identities_root
            / "agents"
            / agent
            / "runtime"
            / "process"
            / process
            / "threads"
            / thread
        )

    def working_memory_path(self, *, agent: str, process: str, thread: str) -> Path:
        return self._thread_root(agent, process, thread) / "working_memory.md"

    def episodic_dir(self, *, agent: str, process: str, thread: str) -> Path:
        return self._thread_root(agent, process, thread) / "episodic"

    def list_episodic_entries(
        self,
        *,
        agent: str,
        process: str,
        thread: str,
    ) -> List[EpisodicEntry]:
        directory = self.episodic_dir(agent=agent, process=process, thread=thread)
        if not directory.exists():
            return []

        entries: List[EpisodicEntry] = []
        for path in sorted(directory.glob("*.md"), reverse=True):
            try:
                fm = load_frontmatter(path)
                metadata = fm.metadata or {}
                author_meta = metadata.get("author") or {}
                author = WorkingMemoryAuthor(
                    agent=author_meta.get("agent", agent),
                    process=author_meta.get("process", process),
                    thread=author_meta.get("thread", thread),
                )
                timestamp_value = metadata.get("timestamp") or metadata.get("created")
                timestamp = ensure_aware_datetime(timestamp_value)
                if timestamp is None:
                    if timestamp_value:
                        logger.warning(
                            "Failed to parse episodic timestamp '%s' in %s; falling back to file mtime.",
                            timestamp_value,
                            path,
                        )
                    timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                header = EpisodicEntryHeader(
                    id=str(metadata.get("id", path.stem)),
                    author=author,
                    timestamp=timestamp,
                    session_type=metadata.get("session_type"),
                    significance=metadata.get("significance"),
                )
                entries.append(
                    EpisodicEntry(
                        header=header,
                        body=fm.body,
                        path=str(path.relative_to(self.identities_root)),
                    )
                )
            except Exception:  # pragma: no cover - defensive
                continue
        return entries

    def read_working_memory(
        self,
        *,
        agent: str,
        process: str,
        thread: str,
    ) -> Optional[WorkingMemoryDocument]:
        path = self.working_memory_path(agent=agent, process=process, thread=thread)
        if not path.exists():
            return None
        fm = load_frontmatter(path)
        metadata = fm.metadata or {}
        updated = ensure_aware_datetime(metadata.get("updated")) or datetime.now(timezone.utc)
        created = ensure_aware_datetime(metadata.get("created"))
        author_meta = metadata.get("author") or {}
        author = WorkingMemoryAuthor(
            agent=author_meta.get("agent", agent),
            process=author_meta.get("process", process),
            thread=author_meta.get("thread", thread),
        )
        return WorkingMemoryDocument(
            id=str(metadata.get("id", f"working-memory-{thread}-{process}")),
            author=author,
            updated=updated,
            created=created,
            content=fm.body,
            path=str(path.relative_to(self.identities_root)),
        )

    def list_summary(
        self,
        *,
        agent: str,
        process: str,
        thread: str,
        limit: int = 5,
        significance: Optional[str] = None,
        session_type: Optional[str] = None,
    ) -> MemorySummary:
        working = self.read_working_memory(agent=agent, process=process, thread=thread)
        episodic_all = self.list_episodic_entries(agent=agent, process=process, thread=thread)
        episodic: List[EpisodicEntry] = []
        for entry in episodic_all:
            header = entry.header
            if significance and header.significance != significance:
                continue
            if session_type and header.session_type != session_type:
                continue
            episodic.append(entry)
            if limit and len(episodic) >= limit:
                break
        return MemorySummary(working=working, episodic=episodic)

    def write_working_memory(
        self,
        *,
        agent: str,
        process: str,
        thread: str,
        author: WorkingMemoryAuthor,
        content: str,
    ) -> WorkingMemoryDocument:
        path = self.working_memory_path(agent=agent, process=process, thread=thread)
        now = datetime.now(timezone.utc)
        existing = load_frontmatter(path) if path.exists() else None
        metadata = dict(existing.metadata) if existing else {}
        metadata.update(
            {
                "id": metadata.get("id") or f"working-memory-{thread}-{process}",
                "author": author.model_dump(mode="json"),
                "updated": now.strftime("%Y-%m-%d-%H-%M-%S"),
            }
        )
        metadata.setdefault("created", metadata["updated"])
        header_text = yaml.safe_dump(metadata, sort_keys=False).strip()
        body = content.rstrip() + "\n" if content.strip() else ""
        text = f"---\n{header_text}\n---\n\n{body}" if body else f"---\n{header_text}\n---\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return WorkingMemoryDocument(
            id=metadata["id"],
            author=author,
            updated=now,
            created=ensure_aware_datetime(metadata.get("created")),
            content=content,
            path=str(path.relative_to(self.identities_root)),
        )

    def append_episodic_entry(
        self,
        *,
        agent: str,
        process: str,
        thread: str,
        author: WorkingMemoryAuthor,
        title: str,
        content: str,
        session_type: Optional[str] = None,
        significance: Optional[str] = None,
    ) -> EpisodicEntry:
        directory = self.episodic_dir(agent=agent, process=process, thread=thread)
        now = datetime.now(timezone.utc)
        timestamp_slug = now.strftime("%Y-%m-%d-%H-%M-%S")
        safe_title = title.strip().lower().replace(" ", "-") or "entry"
        filename = f"{timestamp_slug}-{safe_title}.md"
        path = directory / filename
        metadata = {
            "id": f"episodic-{thread}-{safe_title}",
            "author": author.model_dump(mode="json"),
            "timestamp": timestamp_slug,
            "session_type": session_type,
            "significance": significance,
        }
        header_text = yaml.safe_dump(metadata, sort_keys=False).strip()
        body_text = content.rstrip() + "\n"
        text = f"---\n{header_text}\n---\n\n{body_text}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        header = EpisodicEntryHeader(
            id=metadata["id"],
            author=author,
            timestamp=now,
            session_type=session_type,
            significance=significance,
        )
        return EpisodicEntry(header=header, body=content, path=str(path.relative_to(self.identities_root)))

    def diff_since(
        self,
        *,
        agent: str,
        process: str,
        thread: str,
        since: datetime,
    ) -> List[dict]:
        directory = self.episodic_dir(agent=agent, process=process, thread=thread)
        results: List[dict] = []
        if directory.exists():
            for path in sorted(directory.glob("*.md"), reverse=True):
                fm = load_frontmatter(path)
                timestamp = ensure_aware_datetime(fm.metadata.get("timestamp")) or datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                )
                if timestamp <= since:
                    continue
                results.append(
                    {
                        "path": str(path.relative_to(self.identities_root)),
                        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                        "title": fm.metadata.get("title") or path.stem,
                    }
                )
        working_path = self.working_memory_path(agent=agent, process=process, thread=thread)
        if working_path.exists():
            fm = load_frontmatter(working_path)
            updated = ensure_aware_datetime(fm.metadata.get("updated")) or datetime.fromtimestamp(
                working_path.stat().st_mtime, tz=timezone.utc
            )
            if updated > since:
                results.append(
                    {
                        "path": str(working_path.relative_to(self.identities_root)),
                        "timestamp": updated.isoformat().replace("+00:00", "Z"),
                        "title": fm.metadata.get("title") or "working-memory",
                    }
                )
        return results

    def validate(
        self,
        *,
        agent: str,
        process: str,
        thread: str,
    ) -> dict:
        issues: List[str] = []
        working = self.read_working_memory(agent=agent, process=process, thread=thread)
        episodic = self.list_episodic_entries(agent=agent, process=process, thread=thread)
        if working is None:
            issues.append("Working memory not found")
        if not episodic:
            issues.append("No episodic entries found")
        return {
            "working_exists": working is not None,
            "episodic_count": len(episodic),
            "issues": issues,
        }


def load_frontmatter_entries(paths: Iterable[Path]) -> List[FrontmatterResult]:  # pragma: no cover
    return [load_frontmatter(path) for path in paths]


__all__ = ["AgentThreadFSAdapter"]
