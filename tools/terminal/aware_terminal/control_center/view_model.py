from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Dict, Tuple

from ..integrations.bindings import BindingStore, ThreadBinding
from .models import (
    ControlDataProvider,
    ThreadInfo,
    ThreadStatus,
    ThreadEvent,
)
from ..daemon import ManifestStore, TerminalDaemonClient, manifest_path, DaemonStream, SessionRecord


@dataclass
class ThreadContext:
    process: str
    info: ThreadInfo
    status: ThreadStatus
    binding: Optional[ThreadBinding]

    @property
    def tmux_session(self) -> Optional[str]:
        return self.binding.tmux_session if self.binding else None

    @property
    def workspace(self) -> Optional[int]:
        return self.binding.workspace if self.binding else None


@dataclass
class StreamState:
    client: TerminalDaemonClient
    stream: DaemonStream
    session_id: str
    buffer: str = ""


class ControlCenterViewModel:
    def __init__(self, provider: ControlDataProvider, binding_store: Optional[BindingStore] = None) -> None:
        self.provider = provider
        self.binding_store = binding_store or BindingStore()
        envs = provider.list_environments()
        if not envs:
            raise RuntimeError("No environments available")
        self.environment = envs[0]
        self._threads: List[ThreadContext] = []
        self._events_cache: Dict[str, Tuple[List[ThreadEvent], float]] = {}
        self._streams: Dict[str, "StreamState"] = {}

    def refresh_threads(self, force: bool = False) -> List[ThreadContext]:
        if force:
            self._events_cache.clear()
        entries: List[ThreadContext] = []
        for proc in self.provider.list_processes(self.environment.id):
            for thread in self.provider.list_threads(proc.id):
                status = self.provider.get_thread_status(thread.id)
                binding = self.binding_store.get_thread(thread.id)
                entries.append(ThreadContext(process=proc.name, info=thread, status=status, binding=binding))
        entries.sort(
            key=lambda entry: entry.status.last_event_timestamp or datetime.fromtimestamp(0, tz=timezone.utc),
            reverse=True,
        )
        self._threads = entries
        return entries

    def threads(self) -> List[ThreadContext]:
        if not self._threads:
            return self.refresh_threads()
        return self._threads

    def load_events(self, thread_id: str, force: bool = False) -> List[ThreadEvent]:
        now = time.time()
        cached = self._events_cache.get(thread_id)
        if cached and not force and (now - cached[1]) < 30:
            return cached[0]
        events = self.provider.list_thread_events(thread_id)
        events.sort(key=lambda ev: ev.timestamp, reverse=True)
        self._events_cache[thread_id] = (events, now)
        return events

    def mark_event_reviewed(self, event_id: str, reviewed: bool) -> None:
        self.provider.mark_event_reviewed(event_id, reviewed)
        cached = self._events_cache
        for thread_id, (events, timestamp) in cached.items():
            for idx, ev in enumerate(events):
                if ev.id == event_id:
                    events[idx] = ThreadEvent(
                        id=ev.id,
                        thread_id=ev.thread_id,
                        timestamp=ev.timestamp,
                        descriptor=ev.descriptor,
                        change_type=ev.change_type,
                        doc_path=ev.doc_path,
                        metadata=ev.metadata,
                        reviewed=reviewed,
                    )
                    cached[thread_id] = (events, timestamp)
                    return

    def bind_thread(self, thread_id: str, session: str, workspace: Optional[int]) -> None:
        self.binding_store.set_thread(ThreadBinding(thread_id=thread_id, tmux_session=session, workspace=workspace))
        # update cached thread list
        for idx, entry in enumerate(self._threads):
            if entry.info.id == thread_id:
                self._threads[idx] = ThreadContext(
                    process=entry.process,
                    info=entry.info,
                    status=entry.status,
                    binding=ThreadBinding(thread_id=thread_id, tmux_session=session, workspace=workspace),
                )
                break

    def unbind_thread(self, thread_id: str) -> None:
        if self.binding_store.remove_thread(thread_id):
            for idx, entry in enumerate(self._threads):
                if entry.info.id == thread_id:
                    self._threads[idx] = ThreadContext(
                        process=entry.process,
                        info=entry.info,
                        status=entry.status,
                        binding=None,
                    )
                break

    def get_event_doc(self, event_id: str):
        return self.provider.get_event_doc(event_id)

    # Session streaming -----------------------------------------------------
    def list_sessions(self, thread_id: str) -> List[SessionRecord]:
        client = self._create_daemon_client(thread_id)
        if not client:
            return []
        try:
            return client.list_sessions()
        except Exception:
            return []

    def open_session_stream(self, thread_id: str, cols: int = 80, rows: int = 24) -> bool:
        client = self._create_daemon_client(thread_id)
        if not client:
            return False
        try:
            sessions = client.list_sessions()
            if not sessions:
                return False
            # Prefer session matching thread binding if available
            session_id = self._select_session_id(thread_id, sessions)
            stream = client.attach_stream(session_id, cols, rows)
            self._streams[thread_id] = StreamState(client=client, stream=stream, session_id=session_id, buffer="")
            return True
        except Exception:
            return False

    def close_session_stream(self, thread_id: Optional[str]) -> None:
        if not thread_id:
            return
        handle = self._streams.pop(thread_id, None)
        if handle:
            handle.stream.close()

    def close_all_streams(self) -> None:
        for handle in list(self._streams.values()):
            handle.stream.close()
        self._streams.clear()

    def fetch_session_output(self, thread_id: str) -> Optional[str]:
        handle = self._streams.get(thread_id)
        if not handle:
            return None
        updated = False
        while True:
            event = handle.stream.get_event(timeout=0.0)
            if event is None:
                break
            etype = event.get("type")
            payload = event.get("payload", {})
            if etype == "output":
                data = payload.get("data", "")
                if data:
                    handle.buffer += data
                    if len(handle.buffer) > 8000:
                        handle.buffer = handle.buffer[-8000:]
                    updated = True
            elif etype == "status" and payload.get("status") == "detached":
                self.close_session_stream(thread_id)
                break
        if handle.stream.terminated:
            self.close_session_stream(thread_id)
            return None
        return handle.buffer if updated or handle.buffer else ""

    def is_session_stream_open(self, thread_id: str) -> bool:
        return thread_id in self._streams

    # Internal utilities ----------------------------------------------------
    def _create_daemon_client(self, thread_id: str) -> Optional[TerminalDaemonClient]:
        slug = self._thread_slug(thread_id)
        manifest_file = manifest_path(slug)
        if not manifest_file.exists():
            return None
        store = ManifestStore(manifest_file)
        try:
            manifest = store.load()
        except FileNotFoundError:
            return None
        socket_path = manifest.socket_path
        if not socket_path.exists():
            return None
        return TerminalDaemonClient(socket_path=socket_path, manifest_store=store)

    def _thread_slug(self, thread_id: str) -> str:
        return thread_id.split("/")[-1]

    def _select_session_id(self, thread_id: str, sessions: List[SessionRecord]) -> str:
        binding = self.binding_store.get_thread(thread_id)
        if binding:
            for record in sessions:
                if record.session_id == binding.tmux_session or record.apt_id == binding.tmux_session:
                    return record.session_id
        return sessions[0].session_id
