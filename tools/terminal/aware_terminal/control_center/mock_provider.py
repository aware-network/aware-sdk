from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .models import (
    ControlDataProvider,
    DocumentDescriptor,
    EnvironmentInfo,
    ProcessInfo,
    ThreadDoc,
    ThreadEvent,
    ThreadInfo,
    ThreadStatus,
)

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "mock_data"
DEFAULT_STATE_PATH = Path.home() / ".aware" / "terminal" / "control_center" / "reviewed.json"


class MockControlDataProvider(ControlDataProvider):
    """Loads control-center data from JSON fixtures for offline testing."""

    def __init__(self, fixtures_dir: Path | None = None, state_path: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir or DEFAULT_FIXTURES_DIR
        self.state_path = state_path or DEFAULT_STATE_PATH
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        self._environments = self._load_json("environments.json")
        self._processes = self._load_json("processes.json")
        self._threads = self._load_json("threads.json")
        self._events_cache: dict[str, list[ThreadEvent]] = {}

    def list_environments(self) -> list[EnvironmentInfo]:
        return [
            EnvironmentInfo(
                id=env["id"],
                name=env["name"],
                slug=env["slug"],
                repo_path=Path(env["repo_path"]).expanduser(),
            )
            for env in self._environments
        ]

    def list_processes(self, environment_id: str) -> list[ProcessInfo]:
        return [
            ProcessInfo(
                id=proc["id"],
                name=proc["name"],
                slug=proc["slug"],
                environment_id=proc["environment_id"],
            )
            for proc in self._processes
            if proc["environment_id"] == environment_id
        ]

    def list_threads(self, process_id: str) -> list[ThreadInfo]:
        return [
            ThreadInfo(
                id=th["id"],
                name=th["name"],
                slug=th["slug"],
                process_id=th["process_id"],
                environment_id=th["environment_id"],
                main=th.get("main", False),
                branch_title=th.get("branch_title"),
            )
            for th in self._threads
            if th["process_id"] == process_id
        ]

    def get_thread_status(self, thread_id: str) -> ThreadStatus:
        events = self.list_thread_events(thread_id)
        last_ts = max((ev.timestamp for ev in events), default=None)
        state = self._derive_state(last_ts)
        summary = f"Last update {last_ts.isoformat()}" if last_ts else "No activity recorded"
        return ThreadStatus(thread_id=thread_id, last_event_timestamp=last_ts, state=state, summary=summary)

    def list_thread_events(self, thread_id: str, since: Optional[datetime] = None) -> list[ThreadEvent]:
        events = self._load_events_for_thread(thread_id)
        if since:
            events = [ev for ev in events if ev.timestamp >= since]
        return events

    def get_event_doc(self, event_id: str) -> ThreadDoc:
        doc_path = self.fixtures_dir / "docs" / f"{event_id}.md"
        content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
        return ThreadDoc(event_id=event_id, content=content)

    def mark_event_reviewed(self, event_id: str, reviewed: bool) -> None:
        state = self._load_review_state()
        state[event_id] = reviewed
        self._write_review_state(state)
        for thread_id, events in self._events_cache.items():
            for idx, ev in enumerate(events):
                if ev.id == event_id:
                    events[idx] = replace(ev, reviewed=reviewed)

    # Internal helpers
    def _load_events_for_thread(self, thread_id: str) -> list[ThreadEvent]:
        if thread_id in self._events_cache:
            return self._events_cache[thread_id]

        reviewed_state = self._load_review_state()
        events_path = self.fixtures_dir / "events" / f"{thread_id}.json"
        raw_events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else []
        events: list[ThreadEvent] = []
        for payload in raw_events:
            descriptor = DocumentDescriptor(
                projection=payload.get("projection", "ProjectTaskOPG"),
                channel=payload["channel"],
                label=payload.get("label"),
            )
            events.append(
                ThreadEvent(
                    id=payload["id"],
                    thread_id=payload["thread_id"],
                    timestamp=_parse_timestamp(payload["timestamp"]),
                    descriptor=descriptor,
                    change_type=payload["change_type"],
                    doc_path=Path(payload["doc_path"]),
                    metadata=payload.get("metadata", {}),
                    reviewed=bool(reviewed_state.get(payload["id"], False)),
                )
            )
        self._events_cache[thread_id] = events
        return events

    def _load_json(self, name: str) -> list[dict]:
        path = self.fixtures_dir / name
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_review_state(self) -> dict[str, bool]:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_review_state(self, state: dict[str, bool]) -> None:
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _derive_state(self, last_timestamp: Optional[datetime]) -> str:
        if last_timestamp is None:
            return "idle"
        now = datetime.now(timezone.utc)
        delta = now - last_timestamp
        if delta <= timedelta(hours=2):
            return "active"
        if delta <= timedelta(hours=8):
            return "waiting"
        return "idle"


def _parse_timestamp(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw).astimezone(timezone.utc)
