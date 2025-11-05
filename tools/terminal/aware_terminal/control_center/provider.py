from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, List, Dict

from .models import (
    ControlDataProvider,
    EnvironmentInfo,
    ProcessInfo,
    ThreadInfo,
    ThreadStatus,
    ThreadEvent,
    ThreadDoc,
    DocumentDescriptor,
)
from .mock_provider import MockControlDataProvider  # re-export convenience

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_RUNTIME_ROOT = _REPO_ROOT / "docs" / "runtime" / "process"
_CACHE_TTL = 30.0
_REVIEW_STATE = Path.home() / ".aware" / "terminal" / "control_center" / "reviewed.json"


class CliControlDataProvider(ControlDataProvider):
    def __init__(self, runtime_root: Optional[Path] = None, review_state_path: Optional[Path] = None) -> None:
        if runtime_root is None:
            runtime_root = _DEFAULT_RUNTIME_ROOT
        else:
            runtime_root = runtime_root if runtime_root.is_absolute() else (_REPO_ROOT / runtime_root)
        self.runtime_root = runtime_root
        self.repo_root = runtime_root.parents[2] if len(runtime_root.parents) >= 2 else runtime_root.parent
        self._threads_cache: Optional[Tuple[float, List[dict]]] = None
        self._activity_cache: dict[str, Tuple[float, dict]] = {}
        self._review_state = _ReviewState(review_state_path or _REVIEW_STATE)

    def list_environments(self) -> List[EnvironmentInfo]:
        return [EnvironmentInfo(id="env-local", name="Aware Local", slug="aware-local", repo_path=self.repo_root)]

    def list_processes(self, environment_id: str) -> List[ProcessInfo]:
        threads = self._list_threads()
        processes: Dict[str, Dict[str, str]] = {}
        for item in threads:
            slug = item.get("process_slug", "unknown")
            if slug not in processes:
                processes[slug] = {
                    "id": slug,
                    "slug": slug,
                    "name": item.get("process_title") or item.get("title", slug),
                }
        return [
            ProcessInfo(
                id=data["id"],
                name=data["name"],
                slug=data["slug"],
                environment_id=environment_id,
            )
            for data in processes.values()
        ]

    def list_threads(self, process_id: str) -> List[ThreadInfo]:
        threads_data = [item for item in self._list_threads() if item.get("process_slug") == process_id]
        return [
            ThreadInfo(
                id=item.get("id", f"{process_id}/{item.get('thread_slug')}") or f"{process_id}/{item.get('thread_slug')}",
                name=item.get("title", item.get("thread_slug", "unknown")),
                slug=item.get("thread_slug", "unknown"),
                process_id=process_id,
                environment_id="env-local",
                main=item.get("is_main", False),
                branch_title=item.get("description") or item.get("title"),
            )
            for item in threads_data
        ]

    def get_thread_status(self, thread_id: str) -> ThreadStatus:
        status_payload = self._get_thread_status_payload(thread_id)
        last_event = self._derive_last_event_from_status(status_payload)
        state = _derive_state(last_event)
        summary = status_payload.get("title") or thread_id.split("/", 1)[-1]
        return ThreadStatus(thread_id=thread_id, last_event_timestamp=last_event, state=state, summary=summary)

    def list_thread_events(self, thread_id: str, since: Optional[datetime] = None) -> List[ThreadEvent]:
        status_payload = self._get_thread_status_payload(thread_id)
        events = self._synthetic_events_from_status(thread_id, status_payload)
        review_state = self._review_state.load()
        result: List[ThreadEvent] = []
        for item in events:
            rel_path = item["doc_path"]
            abs_path = self.repo_root / rel_path
            timestamp = item["timestamp"]
            event_id = item["id"]
            result.append(
                ThreadEvent(
                    id=event_id,
                    thread_id=thread_id,
                    timestamp=timestamp,
                    descriptor=DocumentDescriptor(
                        projection=item.get("projection", "runtime"),
                        channel=item.get("channel", "branch"),
                        label=item.get("label"),
                    ),
                    change_type=item.get("change_type", "updated"),
                    doc_path=rel_path,
                    metadata=item.get("metadata", {}),
                    reviewed=bool(review_state.get(event_id)),
                )
            )
        return result

    def get_event_doc(self, event_id: str) -> ThreadDoc:
        path = Path(event_id)
        if not path.is_absolute():
            path = self.repo_root / path
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        return ThreadDoc(event_id=event_id, content=content)

    def mark_event_reviewed(self, event_id: str, reviewed: bool) -> None:
        state = self._review_state.load()
        state[event_id] = reviewed
        self._review_state.save(state)

    # Internal helpers ------------------------------------------------------------------
    def _run_cli_json(self, args: List[str]) -> dict | list:
        cmd = [sys.executable, "-m", "aware_cli.cli"] + args
        result = subprocess.run(
            cmd,
            cwd=_REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"aware-cli failed: {' '.join(args)}\n{result.stderr}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse aware-cli output: {exc}\nOutput: {result.stdout}") from exc

    def _list_threads(self) -> List[dict]:
        now = time.time()
        cached = self._threads_cache
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]
        payload = self._run_cli_json(
            [
                "object",
                "list",
                "--type",
                "thread",
                "--root",
                str(self.runtime_root),
            ]
        )
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected thread list payload")
        self._threads_cache = (now, payload)
        return payload

    def _get_thread_status_payload(self, thread_id: str) -> dict:
        now = time.time()
        cached = self._activity_cache.get(thread_id)
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]
        payload = self._run_cli_json(
            [
                "object",
                "call",
                "--type",
                "thread",
                "--id",
                thread_id,
                "--function",
                "status",
                "--root",
                str(self.runtime_root),
            ]
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected thread status payload")
        self._activity_cache[thread_id] = (now, payload)
        return payload

    def _derive_last_event_from_status(self, payload: dict) -> Optional[datetime]:
        timestamps: List[datetime] = []
        for branch in payload.get("branches", []):
            ts = branch.get("updated_at") or branch.get("branch", {}).get("updated_at")
            if ts:
                timestamps.append(_parse_ts(ts))
        return max(timestamps) if timestamps else None

    def _synthetic_events_from_status(self, thread_id: str, payload: dict) -> List[dict]:
        events: List[dict] = []
        thread_path = Path(payload.get("path", ""))
        for branch in payload.get("branches", []):
            updated_at = branch.get("updated_at") or branch.get("branch", {}).get("updated_at")
            if not updated_at:
                continue
            pane_kind = branch.get("pane_kind", "branch")
            doc_path = thread_path / branch.get("branch_path", "")
            events.append(
                {
                    "id": f"{thread_id}:{pane_kind}",
                    "timestamp": _parse_ts(updated_at),
                    "doc_path": doc_path.relative_to(self.repo_root) if doc_path.is_absolute() else doc_path,
                    "projection": pane_kind,
                    "channel": pane_kind,
                    "label": branch.get("name"),
                    "change_type": "updated",
                    "metadata": {
                        "branch_id": branch.get("branch_id"),
                        "pane_manifest": branch.get("pane_manifest"),
                    },
                }
            )
        events.sort(key=lambda item: item["timestamp"], reverse=True)
        return events


def _derive_state(last_event: Optional[datetime]) -> str:
    if last_event is None:
        return "idle"
    delta = datetime.now(timezone.utc) - last_event
    if delta.total_seconds() <= 7200:
        return "active"
    if delta.total_seconds() <= 28800:
        return "waiting"
    return "idle"


def _parse_ts(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw).astimezone(timezone.utc)


class _ReviewState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, bool]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def save(self, data: dict[str, bool]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
