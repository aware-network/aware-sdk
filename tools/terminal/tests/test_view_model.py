from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
import types

import pytest

from aware_terminal.control_center.models import (
    ControlDataProvider,
    DocumentDescriptor,
    EnvironmentInfo,
    ProcessInfo,
    ThreadDoc,
    ThreadEvent,
    ThreadInfo,
    ThreadStatus,
)
from aware_terminal.control_center.view_model import ControlCenterViewModel
from aware_terminal.integrations.bindings import BindingStore, ThreadBinding


class DummyProvider(ControlDataProvider):
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(hours=1)
        self.environment = EnvironmentInfo(
            id="env-1",
            name="Env One",
            slug="env-one",
            repo_path=Path("/tmp/repo"),
        )
        self.process = ProcessInfo(
            id="proc-1",
            name="Process One",
            slug="process-one",
            environment_id="env-1",
        )
        self.thread_primary = ThreadInfo(
            id="thread-1",
            name="Primary Thread",
            slug="primary-thread",
            process_id="proc-1",
            environment_id="env-1",
        )
        self.thread_secondary = ThreadInfo(
            id="thread-2",
            name="Secondary Thread",
            slug="secondary-thread",
            process_id="proc-1",
            environment_id="env-1",
        )
        self._events: dict[str, List[ThreadEvent]] = {
            "thread-1": [
                ThreadEvent(
                    id="event-1",
                    thread_id="thread-1",
                    timestamp=now,
                    descriptor=DocumentDescriptor(projection="OPG", channel="analysis", label="Analysis"),
                    change_type="updated",
                    doc_path=Path("analysis/doc.md"),
                    metadata={"title": "Analysis Update"},
                    reviewed=False,
                )
            ],
            "thread-2": [
                ThreadEvent(
                    id="event-2",
                    thread_id="thread-2",
                    timestamp=earlier,
                    descriptor=DocumentDescriptor(projection="OPG", channel="design", label="Design"),
                    change_type="created",
                    doc_path=Path("design/doc.md"),
                    metadata={"title": "Design Draft"},
                    reviewed=False,
                )
            ],
        }
        self._docs = {
            "event-1": ThreadDoc(event_id="event-1", content="# Analysis\ncontent"),
            "event-2": ThreadDoc(event_id="event-2", content="# Design\ncontent"),
        }
        self.events_call_count = 0
        self.review_state: dict[str, bool] = {}

    # ControlDataProvider methods ---------------------------------------------------------
    def list_environments(self) -> List[EnvironmentInfo]:
        return [self.environment]

    def list_processes(self, environment_id: str) -> List[ProcessInfo]:
        if environment_id != self.environment.id:
            return []
        return [self.process]

    def list_threads(self, process_id: str) -> List[ThreadInfo]:
        if process_id != self.process.id:
            return []
        return [self.thread_primary, self.thread_secondary]

    def get_thread_status(self, thread_id: str) -> ThreadStatus:
        events = self._events.get(thread_id, [])
        last_ts = max((ev.timestamp for ev in events), default=None)
        return ThreadStatus(
            thread_id=thread_id,
            last_event_timestamp=last_ts,
            state="active" if events else "idle",
            summary="ok",
        )

    def list_thread_events(self, thread_id: str, since: Optional[datetime] = None) -> List[ThreadEvent]:
        self.events_call_count += 1
        events = self._events.get(thread_id, [])
        if since:
            events = [ev for ev in events if ev.timestamp >= since]
        return [replace(ev) for ev in events]

    def get_event_doc(self, event_id: str) -> ThreadDoc:
        return self._docs[event_id]

    def mark_event_reviewed(self, event_id: str, reviewed: bool) -> None:
        for thread_id, events in self._events.items():
            for idx, ev in enumerate(events):
                if ev.id == event_id:
                    events[idx] = replace(ev, reviewed=reviewed)
        self.review_state[event_id] = reviewed


def _build_view_model(tmp_path: Path) -> ControlCenterViewModel:
    provider = DummyProvider()
    store = BindingStore(base=tmp_path)
    return ControlCenterViewModel(provider, binding_store=store)


def test_refresh_threads_sorted_by_last_event(tmp_path: Path) -> None:
    vm = _build_view_model(tmp_path)
    threads = vm.refresh_threads()
    assert [ctx.info.id for ctx in threads] == ["thread-1", "thread-2"]


def test_load_events_uses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vm = _build_view_model(tmp_path)
    provider = vm.provider  # type: ignore[assignment]
    assert isinstance(provider, DummyProvider)

    fake_time = [0.0]

    def _time() -> float:
        return fake_time[0]

    monkeypatch.setattr(
        "aware_terminal.control_center.view_model.time",
        types.SimpleNamespace(time=_time),
    )
    events_first = vm.load_events("thread-1")
    assert len(events_first) == 1
    assert provider.events_call_count == 1

    events_second = vm.load_events("thread-1")
    assert events_second == events_first
    assert provider.events_call_count == 1  # cache hit

    fake_time[0] = 100.0  # force TTL expiration
    events_third = vm.load_events("thread-1")
    assert provider.events_call_count == 2
    assert events_third == events_first

    events_forced = vm.load_events("thread-1", force=True)
    assert provider.events_call_count == 3
    assert events_forced == events_first


def test_mark_event_reviewed_updates_cache(tmp_path: Path) -> None:
    vm = _build_view_model(tmp_path)
    events = vm.load_events("thread-1")
    assert events[0].reviewed is False

    vm.mark_event_reviewed("event-1", True)
    updated = vm.load_events("thread-1")
    assert updated[0].reviewed is True


def test_bind_thread_updates_context(tmp_path: Path) -> None:
    vm = _build_view_model(tmp_path)
    contexts = vm.refresh_threads()
    target = contexts[1]
    assert target.binding is None

    vm.bind_thread("thread-2", "sess", 3)
    refreshed = vm.refresh_threads()
    bound = next(ctx for ctx in refreshed if ctx.info.id == "thread-2")
    assert bound.binding is not None
    assert bound.binding.tmux_session == "sess"
    assert bound.binding.workspace == 3
