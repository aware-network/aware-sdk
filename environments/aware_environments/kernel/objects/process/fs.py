"""Filesystem adapters for orchestrator processes."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .._shared.fs_utils import _safe_load_json, ensure_iso_timestamp, write_json_atomic
from .._shared.runtime_models import RuntimeEvent
from ..thread.schemas import ThreadEntry, ThreadParticipantsManifest
from .._shared.timeline import document_timestamp, ensure_datetime
from .._shared.frontmatter import load_frontmatter
from .schemas import ProcessEntry


class ProcessFSAdapter:
    """Read orchestrator process metadata under docs/runtime/process."""

    def __init__(self, runtime_root: Path) -> None:
        if not isinstance(runtime_root, Path):
            runtime_root = Path(str(runtime_root))
        self.runtime_root = runtime_root.expanduser()

    # ------------------------------------------------------------------
    # Branch + pane manifest helpers
    # ------------------------------------------------------------------

    def _sanitise_pane_kind(self, pane_kind: str) -> str:
        return re.sub(r"[^a-z0-9_-]", "-", pane_kind.lower())

    def _sanitise_branch_id(self, branch_id: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]", "-", branch_id)

    def _branch_dir(self, entry: ThreadEntry, pane_kind: str) -> Path:
        sanitised = self._sanitise_pane_kind(pane_kind)
        return entry.directory / "branches" / sanitised

    def _pane_manifest_dir(self, entry: ThreadEntry, pane_kind: str) -> Path:
        sanitised = self._sanitise_pane_kind(pane_kind)
        return entry.directory / "pane_manifests" / sanitised

    def _branch_file(
        self,
        entry: ThreadEntry,
        pane_kind: str,
        *,
        branch_id: Optional[str] = None,
        legacy: bool = False,
    ) -> Path:
        if branch_id and not legacy:
            sanitised_branch = self._sanitise_branch_id(branch_id)
            return self._branch_dir(entry, pane_kind) / f"{sanitised_branch}.json"

        sanitised = self._sanitise_pane_kind(pane_kind)
        return entry.directory / "branches" / f"{sanitised}.json"

    def _pane_manifest_file(
        self,
        entry: ThreadEntry,
        pane_kind: str,
        *,
        branch_id: Optional[str] = None,
        legacy: bool = False,
    ) -> Path:
        if branch_id and not legacy:
            sanitised_branch = self._sanitise_branch_id(branch_id)
            return self._pane_manifest_dir(entry, pane_kind) / f"{sanitised_branch}.json"

        sanitised = self._sanitise_pane_kind(pane_kind)
        return entry.directory / "pane_manifests" / f"{sanitised}.json"

    def load_branch_manifest(
        self,
        entry: ThreadEntry,
        pane_kind: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, object]:
        branch_path = self._branch_file(entry, pane_kind, branch_id=branch_id)
        branch = _safe_load_json(branch_path) or {}

        # Fall back to legacy layout if nothing was found and no branch_id provided
        if not branch and branch_id is not None:
            legacy_path = self._branch_file(entry, pane_kind, legacy=True)
            branch = _safe_load_json(legacy_path) or {}
            if branch:
                branch_path = legacy_path

        manifest_path = self._pane_manifest_file(entry, pane_kind, branch_id=branch_id)
        manifest = _safe_load_json(manifest_path) or {}
        if not manifest and branch_id is not None:
            legacy_manifest_path = self._pane_manifest_file(entry, pane_kind, legacy=True)
            legacy_manifest = _safe_load_json(legacy_manifest_path) or {}
            if legacy_manifest:
                manifest = legacy_manifest
                manifest_path = legacy_manifest_path

        branch_id_value = branch.get("branch_id") or branch.get("id") or branch_id
        return {
            "pane_kind": pane_kind,
            "branch": branch,
            "branch_id": branch_id_value,
            "branch_path": (
                str(branch_path.relative_to(entry.directory)) if branch_path.exists() else None
            ),
            "pane_manifest": manifest,
            "pane_manifest_path": (
                str(manifest_path.relative_to(entry.directory)) if manifest_path.exists() else None
            ),
        }

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
        branch_path = self._branch_file(entry, pane_kind, branch_id=branch_id)
        manifest_path = self._pane_manifest_file(entry, pane_kind, branch_id=branch_id)
        existing_branch = _safe_load_json(branch_path) or {}
        existing_manifest = _safe_load_json(manifest_path) or {}
        if branch_id is not None and not existing_branch:
            legacy_branch_path = self._branch_file(entry, pane_kind, legacy=True)
            existing_branch = _safe_load_json(legacy_branch_path) or {}
        if branch_id is not None and not existing_manifest:
            legacy_manifest_path = self._pane_manifest_file(entry, pane_kind, legacy=True)
            existing_manifest = _safe_load_json(legacy_manifest_path) or {}

        branch = dict(existing_branch)
        if branch_data:
            branch.update(branch_data)

        branch_id_value = branch_id or branch.get("branch_id") or branch.get("id") or uuid.uuid4().hex
        branch["branch_id"] = branch_id_value
        branch["id"] = branch_id_value
        branch.setdefault("pane_kind", pane_kind)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        branch.setdefault("created_at", existing_branch.get("created_at") or now)
        branch["updated_at"] = now
        branch.setdefault("is_main", bool(existing_branch.get("is_main", False)))

        pane_manifest = dict(existing_manifest)
        pane_manifest.setdefault("pane_kind", pane_kind)
        pane_manifest["branch_id"] = branch_id_value
        pane_manifest["manifest_version"] = manifest_version
        if pane_payload is not None:
            pane_manifest["payload"] = pane_payload
        else:
            pane_manifest.setdefault("payload", existing_manifest.get("payload") or {})

        branch_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(branch_path, branch)
        write_json_atomic(manifest_path, pane_manifest)
        return {
            "branch": branch,
            "pane_manifest": pane_manifest,
            "branch_path": str(branch_path.relative_to(entry.directory)),
            "pane_manifest_path": str(manifest_path.relative_to(entry.directory)),
        }

    def update_thread_task_binding(self, entry: ThreadEntry, binding: dict) -> None:
        thread_json_path = entry.directory / "thread.json"
        data = _safe_load_json(thread_json_path) or {}
        tasks = data.get("thread_task_list")
        if not isinstance(tasks, list):
            tasks = []
        tasks = [item for item in tasks if isinstance(item, dict) and item.get("task_id") != binding.get("task_id")]
        tasks.append(binding)
        data["thread_task_list"] = tasks
        write_json_atomic(thread_json_path, data)

    def refresh_branch(
        self,
        entry: ThreadEntry,
        pane_kind: str,
        branch_id: Optional[str] = None,
    ) -> dict:
        data = self.load_branch_manifest(entry, pane_kind, branch_id=branch_id)
        if not data.get("branch"):
            raise ValueError(f"Branch '{pane_kind}' not found for thread {entry.thread_slug}")
        branch_payload = dict(data["branch"])
        branch_payload.pop("updated_at", None)
        pane_payload = data.get("pane_manifest", {}).get("payload")
        return self.write_branch_manifest(
            entry,
            pane_kind,
            branch_id=data.get("branch_id"),
            branch_data=branch_payload,
            pane_payload=pane_payload,
            manifest_version=data.get("pane_manifest", {}).get("manifest_version", 1),
        )

    def migrate_singleton_branch(
        self,
        entry: ThreadEntry,
        pane_kind: str,
    ) -> dict:
        legacy_branch_path = self._branch_file(entry, pane_kind, legacy=True)
        legacy_manifest_path = self._pane_manifest_file(entry, pane_kind, legacy=True)
        has_legacy = legacy_branch_path.exists() or legacy_manifest_path.exists()
        if not has_legacy:
            return {
                "pane_kind": pane_kind,
                "migrated": False,
                "reason": "legacy_missing",
            }

        legacy_branch = _safe_load_json(legacy_branch_path) or {}
        legacy_manifest = _safe_load_json(legacy_manifest_path) or {}

        branch_id = (
            legacy_branch.get("branch_id")
            or legacy_branch.get("id")
            or legacy_manifest.get("branch_id")
        )
        if branch_id is None:
            branch_id = uuid.uuid4().hex
        else:
            branch_id = str(branch_id)

        legacy_branch.setdefault("pane_kind", pane_kind)
        legacy_branch["branch_id"] = branch_id
        legacy_branch["id"] = branch_id
        legacy_branch.setdefault("is_main", bool(legacy_branch.get("is_main")))

        manifest_version = legacy_manifest.get("manifest_version", 1)
        pane_payload = legacy_manifest.get("payload")

        new_branch_path = self._branch_file(
            entry, pane_kind, branch_id=branch_id
        )
        new_manifest_path = self._pane_manifest_file(
            entry, pane_kind, branch_id=branch_id
        )

        if new_branch_path.exists() and new_manifest_path.exists():
            # Already migrated; delete legacy if still present
            if legacy_branch_path.exists():
                legacy_branch_path.unlink()
            if legacy_manifest_path.exists():
                legacy_manifest_path.unlink()
            return {
                "pane_kind": pane_kind,
                "branch_id": branch_id,
                "branch_path": str(new_branch_path.relative_to(entry.directory)),
                "pane_manifest_path": str(new_manifest_path.relative_to(entry.directory)),
                "migrated": False,
                "reason": "already_migrated",
            }

        result = self.write_branch_manifest(
            entry,
            pane_kind,
            branch_id=branch_id,
            branch_data=legacy_branch,
            pane_payload=pane_payload,
            manifest_version=manifest_version,
        )

        if legacy_branch_path.exists():
            legacy_branch_path.unlink()
        if legacy_manifest_path.exists():
            legacy_manifest_path.unlink()

        return {
            "pane_kind": pane_kind,
            "branch_id": branch_id,
            "branch_path": result["branch_path"],
            "pane_manifest_path": result["pane_manifest_path"],
            "migrated": True,
        }

    def load_participants_manifest(self, entry: ThreadEntry) -> ThreadParticipantsManifest:
        manifest_path = entry.directory / "participants.json"
        data = _safe_load_json(manifest_path)
        if data:
            return ThreadParticipantsManifest.model_validate(data)

        now = datetime.now(timezone.utc)
        identifier = entry.thread_id or f"{entry.process_slug}/{entry.thread_slug}"
        return ThreadParticipantsManifest(
            version=1,
            thread_id=identifier,
            process_slug=entry.process_slug,
            updated_at=now,
            participants=[],
        )

    def write_participants_manifest(
        self,
        entry: ThreadEntry,
        manifest: ThreadParticipantsManifest,
    ) -> ThreadParticipantsManifest:
        manifest_path = entry.directory / "participants.json"
        manifest.updated_at = datetime.now(timezone.utc)
        write_json_atomic(manifest_path, manifest.model_dump_json_ready())
        return manifest

    # ------------------------------------------------------------------
    # Process listings
    # ------------------------------------------------------------------

    def list_processes(self, status: Optional[str] = None) -> List[ProcessEntry]:
        if not self.runtime_root.exists():
            return []

        entries: List[ProcessEntry] = []
        for process_dir in sorted(path for path in self.runtime_root.iterdir() if path.is_dir()):
            entry = self._load_process(process_dir)
            if not entry:
                continue
            if status and entry.status and entry.status.lower() != status.lower():
                continue
            entries.append(entry)
        return entries

    def get_process(self, identifier: str) -> Optional[ProcessEntry]:
        process_dir = self.runtime_root / identifier
        if process_dir.exists():
            return self._load_process(process_dir)

        for candidate in self.runtime_root.iterdir():
            if not candidate.is_dir():
                continue
            entry = self._load_process(candidate)
            if entry and entry.process_id and entry.process_id == identifier:
                return entry
        return None

    def collect_backlog(
        self,
        entry: ProcessEntry,
        *,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[RuntimeEvent]:
        backlog_dir = entry.directory / "backlog"
        if not backlog_dir.exists():
            return []

        events: List[RuntimeEvent] = []
        for path in sorted(backlog_dir.glob("*.md"), reverse=True):
            frontmatter = load_frontmatter(path)
            timestamp = document_timestamp(
                path,
                frontmatter.metadata,
                extra_candidates=[path.stat().st_mtime],
            )
            if since and timestamp <= since:
                continue
            summary = frontmatter.metadata.get("title") or path.stem
            events.append(
                RuntimeEvent(
                    event_id=str(path.relative_to(entry.directory)),
                    event_type="backlog",
                    timestamp=timestamp,
                    path=path,
                    summary=str(summary),
                    metadata=frontmatter.metadata,
                )
            )
            if limit and len(events) >= limit:
                break
        return events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_process(self, process_dir: Path) -> Optional[ProcessEntry]:
        process_json_path = process_dir / "process.json"
        data = _safe_load_json(process_json_path)
        if not data:
            return None

        threads_dir = process_dir / "threads"
        thread_count = sum(1 for _ in threads_dir.iterdir()) if threads_dir.exists() else 0

        latest_backlog = None
        backlog_dir = process_dir / "backlog"
        if backlog_dir.exists():
            for path in backlog_dir.glob("*.md"):
                frontmatter = load_frontmatter(path)
                ts = document_timestamp(
                    path,
                    frontmatter.metadata,
                    extra_candidates=[path.stat().st_mtime],
                )
                if not latest_backlog or ts > latest_backlog:
                    latest_backlog = ts

        return ProcessEntry(
            slug=process_dir.name,
            directory=process_dir,
            process_id=str(data.get("id")) if data.get("id") else None,
            title=str(data.get("title")) if data.get("title") else None,
            description=str(data.get("description")) if data.get("description") else None,
            priority_level=str(data.get("priority_level")) if data.get("priority_level") else None,
            status=str(data.get("status")) if data.get("status") else None,
            thread_count=thread_count,
            latest_backlog_at=latest_backlog,
            created_at=ensure_datetime(data.get("created_at")),
            updated_at=ensure_datetime(data.get("updated_at")),
        )


__all__ = ["ProcessFSAdapter", "ensure_iso_timestamp"]
