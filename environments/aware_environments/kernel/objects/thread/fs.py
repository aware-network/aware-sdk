"""Filesystem adapters for agent threads."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import re

from .._shared.fs_utils import _safe_load_json, ensure_iso_timestamp
from .._shared.runtime_models import RuntimeEvent
from .._shared.timeline import document_timestamp, ensure_datetime
from .._shared.frontmatter import load_frontmatter
from .schemas import ThreadEntry, ThreadParticipantsManifest


class ThreadFSAdapter:
    """Read thread metadata under docs/runtime/process/<process>/threads."""

    def __init__(self, runtime_root: Path) -> None:
        if not isinstance(runtime_root, Path):
            runtime_root = Path(str(runtime_root))
        self.runtime_root = runtime_root.expanduser()

    def _branch_file(self, entry: ThreadEntry, pane_kind: str) -> Path:
        sanitised = re.sub(r"[^a-z0-9_-]", "-", pane_kind.lower())
        return entry.directory / "branches" / f"{sanitised}.json"

    def _pane_manifest_file(self, entry: ThreadEntry, pane_kind: str) -> Path:
        sanitised = re.sub(r"[^a-z0-9_-]", "-", pane_kind.lower())
        return entry.directory / "pane_manifests" / f"{sanitised}.json"

    def load_branch_manifest(
        self,
        entry: ThreadEntry,
        pane_kind: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, object]:
        from ..process.fs import ProcessFSAdapter  # local import to avoid cycle

        adapter = ProcessFSAdapter(self.runtime_root)
        return adapter.load_branch_manifest(entry, pane_kind, branch_id=branch_id)

    def write_branch_manifest(
        self,
        entry: ThreadEntry,
        pane_kind: str,
        branch_id: Optional[str] = None,
        *,
        branch_data: Optional[dict] = None,
        pane_payload: Optional[dict] = None,
        manifest_version: int = 1,
    ) -> dict:
        from ..process.fs import ProcessFSAdapter  # local import

        adapter = ProcessFSAdapter(self.runtime_root)
        return adapter.write_branch_manifest(
            entry,
            pane_kind,
            branch_id=branch_id,
            branch_data=branch_data,
            pane_payload=pane_payload,
            manifest_version=manifest_version,
        )

    def refresh_branch(
        self,
        entry: ThreadEntry,
        pane_kind: str,
        branch_id: Optional[str] = None,
    ) -> dict:
        from ..process.fs import ProcessFSAdapter  # local import

        adapter = ProcessFSAdapter(self.runtime_root)
        return adapter.refresh_branch(entry, pane_kind, branch_id=branch_id)

    def migrate_singleton_branch(
        self,
        entry: ThreadEntry,
        pane_kind: str,
    ) -> dict:
        from ..process.fs import ProcessFSAdapter  # local import

        adapter = ProcessFSAdapter(self.runtime_root)
        return adapter.migrate_singleton_branch(entry, pane_kind)

    def update_thread_task_binding(self, entry: ThreadEntry, binding: dict) -> None:
        from ..process.fs import ProcessFSAdapter  # local import

        adapter = ProcessFSAdapter(self.runtime_root)
        adapter.update_thread_task_binding(entry, binding)

    def list_threads(self, process_slug: Optional[str] = None) -> List[ThreadEntry]:
        if not self.runtime_root.exists():
            return []

        entries: List[ThreadEntry] = []
        for process_dir in sorted(path for path in self.runtime_root.iterdir() if path.is_dir()):
            if process_slug and process_dir.name != process_slug:
                continue
            threads_dir = process_dir / "threads"
            if not threads_dir.exists():
                continue
            for thread_dir in sorted(path for path in threads_dir.iterdir() if path.is_dir()):
                entry = self._load_thread(process_dir.name, thread_dir)
                if entry:
                    entries.append(entry)
        return entries

    def get_thread(self, identifier: str) -> Optional[ThreadEntry]:
        if "/" in identifier:
            process_slug, thread_slug = identifier.split("/", 1)
        else:
            process_slug, thread_slug = identifier, "main"
        thread_dir = self.runtime_root / process_slug / "threads" / thread_slug
        if thread_dir.exists():
            return self._load_thread(process_slug, thread_dir)

        for process_dir in self.runtime_root.iterdir():
            if not process_dir.is_dir():
                continue
            threads_dir = process_dir / "threads"
            if not threads_dir.exists():
                continue
            for candidate in threads_dir.iterdir():
                if not candidate.is_dir():
                    continue
                entry = self._load_thread(process_dir.name, candidate)
                if entry and entry.thread_id == identifier:
                    return entry
        return None

    def list_activity(self, entry: ThreadEntry, *, since: Optional[datetime] = None) -> List[RuntimeEvent]:
        events: List[RuntimeEvent] = []

        def _maybe_add(path: Path, event_type: str, summary: Optional[str] = None) -> None:
            frontmatter = load_frontmatter(path)
            timestamp = document_timestamp(
                path,
                frontmatter.metadata,
                extra_candidates=[path.stat().st_mtime],
            )
            if since and timestamp <= since:
                return
            label = summary or frontmatter.metadata.get("title") or path.stem
            events.append(
                RuntimeEvent(
                    event_id=str(path.relative_to(entry.directory)),
                    event_type=event_type,
                    timestamp=timestamp,
                    path=path,
                    summary=str(label),
                    metadata=frontmatter.metadata,
                )
            )

        overview_path = entry.directory / "OVERVIEW.md"
        if overview_path.exists():
            _maybe_add(overview_path, "overview")

        backlog_dir = entry.directory / "backlog"
        if backlog_dir.exists():
            for path in sorted(backlog_dir.glob("*.md"), reverse=True):
                _maybe_add(path, "backlog")

        conversations_dir = entry.directory / "conversations"
        if conversations_dir.exists():
            for path in sorted(conversations_dir.glob("*.md"), reverse=True):
                _maybe_add(path, "conversation")

        events.sort(key=lambda evt: evt.timestamp, reverse=True)
        return events

    def collect_activity(self, entry: ThreadEntry, *, since: Optional[datetime] = None) -> List[RuntimeEvent]:
        return self.list_activity(entry, since=since)

    def list_branches(self, entry: ThreadEntry) -> List[dict]:
        branches_dir = entry.directory / "branches"
        if not branches_dir.exists():
            return []

        branches: List[dict] = []

        # New layout: branches/<pane_kind>/*.json
        for pane_dir in sorted(path for path in branches_dir.iterdir() if path.is_dir()):
            for branch_file in sorted(pane_dir.glob("*.json")):
                branch_id = branch_file.stem
                pane_kind_slug = pane_dir.name
                data = self.load_branch_manifest(entry, pane_kind_slug, branch_id=branch_id)
                branch = data.get("branch") or {}
                if not branch:
                    continue
                pane_kind = branch.get("pane_kind") or pane_kind_slug
                resolved_branch_id = str(branch.get("branch_id") or branch.get("id") or branch_id)
                branches.append(
                    {
                        "pane_kind": pane_kind,
                        "branch_id": resolved_branch_id,
                        "id": resolved_branch_id,
                        "name": branch.get("name"),
                        "is_main": branch.get("is_main"),
                        "created_at": branch.get("created_at"),
                        "updated_at": branch.get("updated_at"),
                        "branch": branch,
                        "branch_path": data.get("branch_path"),
                        "pane_manifest": data.get("pane_manifest"),
                        "pane_manifest_path": data.get("pane_manifest_path"),
                        "path": data.get("branch_path"),
                        "manifest_path": data.get("pane_manifest_path"),
                    }
                )

        # Legacy layout: branches/<pane_kind>.json
        for branch_file in sorted(path for path in branches_dir.glob("*.json") if path.is_file()):
            pane_kind_slug = branch_file.stem
            data = self.load_branch_manifest(entry, pane_kind_slug)
            branch = data.get("branch") or {}
            if not branch:
                continue
            pane_kind = branch.get("pane_kind") or pane_kind_slug
            branch_id = str(branch.get("branch_id") or branch.get("id") or pane_kind_slug)
            branches.append(
                {
                    "pane_kind": pane_kind,
                    "branch_id": branch_id,
                    "id": branch_id,
                    "name": branch.get("name"),
                    "is_main": branch.get("is_main"),
                    "created_at": branch.get("created_at"),
                    "updated_at": branch.get("updated_at"),
                    "branch": branch,
                    "branch_path": data.get("branch_path"),
                    "pane_manifest": data.get("pane_manifest"),
                    "pane_manifest_path": data.get("pane_manifest_path"),
                    "path": data.get("branch_path"),
                    "manifest_path": data.get("pane_manifest_path"),
                }
            )
        return branches

    def list_conversations(
        self,
        entry: ThreadEntry,
        *,
        since: Optional[datetime] = None,
    ) -> List[dict]:
        conversations_dir = entry.directory / "conversations"
        if not conversations_dir.exists():
            return []

        entries: List[dict] = []
        for path in sorted(conversations_dir.glob("*.md")):
            frontmatter = load_frontmatter(path)
            timestamp = document_timestamp(
                path,
                frontmatter.metadata,
                extra_candidates=[path.stat().st_mtime],
            )
            if since and timestamp <= since:
                continue
            entries.append(
                {
                    "conversation_id": frontmatter.metadata.get("conversation_id"),
                    "title": frontmatter.metadata.get("title"),
                    "updated_at": ensure_iso_timestamp(timestamp),
                    "path": str(path.relative_to(entry.directory)),
                }
            )
        return entries

    def load_participants_manifest(self, entry: ThreadEntry) -> ThreadParticipantsManifest:
        from ..process.fs import ProcessFSAdapter  # local import

        adapter = ProcessFSAdapter(self.runtime_root)
        return adapter.load_participants_manifest(entry)

    def write_participants_manifest(
        self,
        entry: ThreadEntry,
        manifest: ThreadParticipantsManifest,
    ) -> ThreadParticipantsManifest:
        from ..process.fs import ProcessFSAdapter  # local import

        adapter = ProcessFSAdapter(self.runtime_root)
        return adapter.write_participants_manifest(entry, manifest)

    def load_document(self, entry: ThreadEntry, relative_path: str) -> Path:
        target = (entry.directory / relative_path).resolve()
        target.relative_to(entry.directory)
        if not target.exists():
            raise FileNotFoundError(f"Document not found: {relative_path}")
        return target

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_thread(self, process_slug: str, thread_dir: Path) -> Optional[ThreadEntry]:
        thread_json_path = thread_dir / "thread.json"
        data = _safe_load_json(thread_json_path)
        if not data:
            return None

        branches_dir = thread_dir / "branches"
        branch_count = 0
        pane_kinds: List[str] = []
        if branches_dir.exists():
            for branch_file in branches_dir.glob("*.json"):
                branch_data = _safe_load_json(branch_file)
                if not branch_data:
                    continue
                branch_count += 1
                pane_kind = branch_data.get("pane_kind")
                if pane_kind and pane_kind not in pane_kinds:
                    pane_kinds.append(pane_kind)

        conversations_dir = thread_dir / "conversations"
        conversation_count = (
            sum(1 for _ in conversations_dir.glob("*.md")) if conversations_dir.exists() else 0
        )

        return ThreadEntry(
            process_slug=process_slug,
            thread_slug=thread_dir.name,
            directory=thread_dir,
            thread_id=str(data.get("id")) if data.get("id") else None,
            process_id=str(data.get("process_id")) if data.get("process_id") else None,
            title=str(data.get("title")) if data.get("title") else None,
            description=str(data.get("description")) if data.get("description") else None,
            is_main=bool(data.get("is_main", False)),
            branch_count=branch_count,
            pane_kinds=tuple(pane_kinds),
            conversation_count=conversation_count,
            created_at=ensure_datetime(data.get("created_at")),
            updated_at=ensure_datetime(data.get("updated_at")),
        )


__all__ = ["ThreadFSAdapter"]
