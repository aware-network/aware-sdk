from __future__ import annotations

import curses
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from ..view_model import ControlCenterViewModel, ThreadContext
from ..models import ThreadEvent
from .components import (
    PaneDimensions,
    draw_events_list,
    draw_footer,
    draw_header,
    draw_threads_list,
    safe_addnstr,
)
from .markdown_view import MarkdownView
from .status_panel import build_status_line


@dataclass
class ControlAction:
    action: str  # "attach" | "none"
    thread_id: Optional[str] = None
    tmux_session: Optional[str] = None


@dataclass
class ControlState:
    environment_name: str
    view_model: ControlCenterViewModel
    entries: List[ThreadContext]
    selected_thread: int = 0
    selected_event: int = 0
    filter_text: str = ""
    doc_view: Optional[MarkdownView] = None
    doc_open: bool = False
    session_mode: bool = False
    session_thread_id: Optional[str] = None
    session_text: str = ""
    session_error: Optional[str] = None

    @property
    def filtered_threads(self) -> List[ThreadContext]:
        if not self.filter_text:
            return self.entries
        lowered = self.filter_text.lower()
        return [
            entry
            for entry in self.entries
            if lowered in entry.info.name.lower()
            or lowered in entry.process.lower()
            or lowered in entry.info.id.lower()
        ]


def run_control_center(view_model: ControlCenterViewModel) -> ControlAction:
    threads = view_model.refresh_threads()
    if not threads:
        raise RuntimeError("No threads available to display.")

    environment_name = view_model.environment.name
    state = ControlState(environment_name=environment_name, view_model=view_model, entries=threads)

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        _print_summary(state.entries)
        return ControlAction("none")

    try:
        return curses.wrapper(_main_loop, state)
    except curses.error:
        _print_summary(state.entries)
        return ControlAction("none")


def _main_loop(stdscr, state: ControlState) -> ControlAction:
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)
    try:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
    except Exception:
        pass

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        draw_header(stdscr, width, state.environment_name, state.filter_text)

        content_top = 3
        footer_row = height - 1
        content_height = max(0, footer_row - content_top)

        threads, selected_thread_index = _ensure_selection(state)
        events = _load_events(state, threads, selected_thread_index)
        selected_event_index = _ensure_event_selection(state, events)

        layout = _compute_layout(width, content_top, content_height)
        draw_threads_list(
            stdscr,
            layout["threads"],
            threads,
            selected_thread_index,
        )
        draw_events_list(
            stdscr,
            layout["events"],
            events,
            selected_event_index,
        )
        doc_dims = layout["docs"]
        selected = threads[selected_thread_index] if threads else None
        _render_doc_panel(stdscr, state, events, selected_event_index, doc_dims, selected)
        status_line = build_status_line(selected, events)
        draw_footer(stdscr, footer_row, width, status_line)
        stdscr.refresh()

        key = stdscr.getch()
        action = _handle_key(stdscr, key, state, threads, events, doc_dims)
        if action is not None:
            state.view_model.close_all_streams()
            return action


def _ensure_selection(state: ControlState) -> Tuple[List[ThreadContext], int]:
    threads = state.filtered_threads
    if not threads:
        state.selected_thread = 0
        return [], 0
    state.selected_thread = max(0, min(state.selected_thread, len(threads) - 1))
    return threads, state.selected_thread


def _load_events(
    state: ControlState,
    threads: Sequence[ThreadContext],
    selected_index: int,
) -> List[ThreadEvent]:
    if not threads:
        return []
    thread = threads[selected_index]
    events = state.view_model.load_events(thread.info.id)
    return events


def _ensure_event_selection(state: ControlState, events: Sequence[ThreadEvent]) -> int:
    if not events:
        state.selected_event = 0
        return 0
    state.selected_event = max(0, min(state.selected_event, len(events) - 1))
    return state.selected_event


def _render_doc_panel(
    stdscr,
    state: ControlState,
    events: Sequence[ThreadEvent],
    selected_index: int,
    dims: PaneDimensions,
    selected: Optional[ThreadContext],
) -> None:
    try:
        doc_win = stdscr.derwin(dims.height, dims.width, dims.y, dims.x)
    except curses.error:
        return
    doc_win.erase()

    if state.session_mode:
        _render_session_panel(doc_win, state, dims, selected)
        return

    if not state.doc_open:
        safe_addnstr(doc_win, 0, 0, "Doc Preview (press 'd' to open)".ljust(dims.width), dims.width, curses.A_UNDERLINE)
        if events:
            safe_addnstr(doc_win, 1, 0, "Select an event and press 'd' to load.".ljust(dims.width), dims.width, curses.A_DIM)
        else:
            safe_addnstr(doc_win, 1, 0, "No events available.".ljust(dims.width), dims.width, curses.A_DIM)
        return

    if not events:
        safe_addnstr(doc_win, 0, 0, "Doc Preview".ljust(dims.width), dims.width, curses.A_UNDERLINE)
        safe_addnstr(doc_win, 1, 0, "No events to display.".ljust(dims.width), dims.width, curses.A_DIM)
        return

    if selected_index >= len(events):
        safe_addnstr(doc_win, 0, 0, "Doc Preview".ljust(dims.width), dims.width, curses.A_UNDERLINE)
        return

    event = events[selected_index]
    if state.doc_view is None or state.doc_view.doc.event_id != event.id:
        doc = state.view_model.get_event_doc(event.id)
        state.doc_view = MarkdownView(doc=doc)
        state.view_model.mark_event_reviewed(event.id, True)
    title = event.metadata.get("title") or event.descriptor.label or event.doc_path.name
    state.doc_view.render(doc_win, dims.height, dims.width, f"Doc: {title} — q to close")


def _render_session_panel(doc_win, state: ControlState, dims: PaneDimensions, selected: Optional[ThreadContext]) -> None:
    header = "Session Stream (press 't' to close)"
    safe_addnstr(doc_win, 0, 0, header.ljust(dims.width), dims.width, curses.A_UNDERLINE)

    if not selected or not state.session_thread_id or selected.info.id != state.session_thread_id:
        safe_addnstr(doc_win, 1, 0, "Select a thread to stream.".ljust(dims.width), dims.width, curses.A_DIM)
        state.session_mode = False
        state.session_thread_id = None
        return

    thread_id = state.session_thread_id

    if not state.view_model.is_session_stream_open(thread_id):
        opened = state.view_model.open_session_stream(thread_id, cols=dims.width, rows=max(1, dims.height - 2))
        if not opened:
            message = state.session_error or "Daemon unavailable or no sessions registered."
            safe_addnstr(doc_win, 1, 0, message.ljust(dims.width), dims.width, curses.A_DIM)
            state.session_error = message
            state.session_mode = False
            state.session_thread_id = None
            return
        state.session_error = None

    output = state.view_model.fetch_session_output(thread_id)
    if output is None:
        safe_addnstr(doc_win, 1, 0, "Stream ended.".ljust(dims.width), dims.width, curses.A_DIM)
        state.view_model.close_session_stream(thread_id)
        state.session_mode = False
        state.session_thread_id = None
        return
    if output:
        state.session_text = output

    lines = state.session_text.splitlines()
    max_rows = max(0, dims.height - 2)
    start = max(0, len(lines) - max_rows)
    visible = lines[start : start + max_rows]
    if not visible:
        safe_addnstr(doc_win, 1, 0, "Waiting for output...".ljust(dims.width), dims.width, curses.A_DIM)
        return
    for idx, line in enumerate(visible):
        safe_addnstr(doc_win, 1 + idx, 0, line.ljust(dims.width), dims.width)


def _handle_key(
    stdscr,
    key: int,
    state: ControlState,
    threads: Sequence[ThreadContext],
    events: Sequence[ThreadEvent],
    doc_dims: PaneDimensions,
) -> Optional[ControlAction]:
    if state.doc_open and state.doc_view is not None:
        if key in (ord("d"), ord("v")):
            state.doc_open = False
            state.doc_view = None
            return None
        exit_doc = state.doc_view.handle_key(key, doc_dims.height)
        if exit_doc:
            state.doc_open = False
            state.doc_view = None
        return None

    if key in (ord("q"), 27):
        return ControlAction("none")
    if key in (curses.KEY_DOWN, ord("j")):
        if threads:
            state.selected_thread = min(state.selected_thread + 1, len(threads) - 1)
            state.selected_event = 0
            if state.session_mode:
                state.view_model.close_session_stream(state.session_thread_id)
                state.session_mode = False
                state.session_thread_id = None
                state.session_text = ""
                state.session_error = None
    elif key in (curses.KEY_UP, ord("k")):
        if threads:
            state.selected_thread = max(state.selected_thread - 1, 0)
            state.selected_event = 0
            if state.session_mode:
                state.view_model.close_session_stream(state.session_thread_id)
                state.session_mode = False
                state.session_thread_id = None
                state.session_text = ""
                state.session_error = None
    elif key in (curses.KEY_RIGHT, ord("l")):
        if events:
            state.selected_event = min(state.selected_event + 1, len(events) - 1)
    elif key in (curses.KEY_LEFT, ord("h")):
        if events:
            state.selected_event = max(state.selected_event - 1, 0)
    elif key == ord("/"):
        _prompt_filter(stdscr, state)
    elif key == ord("r"):
        state.entries = state.view_model.refresh_threads(force=False)
    elif key == ord("R"):
        state.entries = state.view_model.refresh_threads(force=True)
    elif key == ord("m"):
        if events:
            event = events[state.selected_event]
            state.view_model.mark_event_reviewed(event.id, not event.reviewed)
            state.doc_view = None
    elif key in (ord("d"), ord("v")):
        if events:
            state.doc_open = not state.doc_open
            if not state.doc_open:
                state.doc_view = None
            state.session_mode = False
            if state.session_thread_id:
                state.view_model.close_session_stream(state.session_thread_id)
                state.session_thread_id = None
                state.session_text = ""
                state.session_error = None
    elif key == ord("b"):
        if threads:
            entry = threads[state.selected_thread]
            binding = _prompt_binding(stdscr, entry)
            if binding:
                state.view_model.bind_thread(entry.info.id, binding[0], binding[1])
                state.entries = state.view_model.refresh_threads(force=False)
    elif key == ord("t"):
        if state.session_mode:
            state.view_model.close_session_stream(state.session_thread_id)
            state.session_mode = False
            state.session_thread_id = None
            state.session_text = ""
            state.session_error = None
        elif threads:
            entry = threads[state.selected_thread]
            state.session_mode = True
            state.session_thread_id = entry.info.id
            state.session_text = ""
            state.session_error = None
            state.doc_open = False
            state.doc_view = None
        else:
            state.session_error = "No thread selected for streaming"
    elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
        if threads:
            entry = threads[state.selected_thread]
            session = entry.binding.tmux_session if entry.binding else None
            if session:
                return ControlAction("attach", thread_id=entry.info.id, tmux_session=session)
            binding = _prompt_binding(stdscr, entry)
            if binding:
                state.view_model.bind_thread(entry.info.id, binding[0], binding[1])
                state.entries = state.view_model.refresh_threads(force=False)
    return None


def _prompt_filter(stdscr, state: ControlState) -> None:
    curses.echo()
    height, width = stdscr.getmaxyx()
    prompt = "Filter threads: "
    safe_addnstr(stdscr, 2, 0, prompt.ljust(width), width, curses.A_DIM)
    stdscr.refresh()
    try:
        text = stdscr.getstr(2, len(prompt), 60)
    except Exception:
        text = b""
    curses.noecho()
    state.filter_text = text.decode("utf-8").strip() if text else ""
    state.selected_thread = 0
    state.selected_event = 0


def _prompt_binding(stdscr, entry: ThreadContext) -> Optional[Tuple[str, Optional[int]]]:
    curses.echo()
    height, width = stdscr.getmaxyx()
    prompt_session = f"tmux session for {entry.info.id}: "
    safe_addnstr(stdscr, height - 3, 0, prompt_session.ljust(width), width, curses.A_DIM)
    stdscr.refresh()
    try:
        session = stdscr.getstr(height - 3, len(prompt_session), 64)
    except Exception:
        session = b""
    if not session:
        curses.noecho()
        return None
    prompt_workspace = "workspace (optional): "
    safe_addnstr(stdscr, height - 2, 0, prompt_workspace.ljust(width), width, curses.A_DIM)
    stdscr.refresh()
    try:
        workspace = stdscr.getstr(height - 2, len(prompt_workspace), 6)
    except Exception:
        workspace = b""
    curses.noecho()
    session_str = session.decode("utf-8").strip()
    workspace_str = workspace.decode("utf-8").strip() if workspace else ""
    workspace_int = int(workspace_str) if workspace_str.isdigit() else None
    return session_str, workspace_int


def _compute_layout(width: int, top: int, height: int) -> dict[str, PaneDimensions]:
    threads_width = max(32, width // 3)
    events_width = max(32, width // 3)
    docs_width = max(20, width - threads_width - events_width - 2)
    threads_dims = PaneDimensions(y=top, x=0, height=height, width=threads_width)
    events_dims = PaneDimensions(y=top, x=threads_width + 1, height=height, width=events_width)
    docs_dims = PaneDimensions(y=top, x=threads_width + events_width + 2, height=height, width=docs_width)
    return {"threads": threads_dims, "events": events_dims, "docs": docs_dims}


def _print_summary(entries: Sequence[ThreadContext]) -> None:
    print("Control Center (non-interactive)")
    for entry in entries:
        last = entry.status.last_event_timestamp.isoformat() if entry.status.last_event_timestamp else "--"
        binding = ""
        if entry.binding and entry.binding.tmux_session:
            ws = f" ws{entry.binding.workspace}" if entry.binding.workspace is not None else ""
            binding = f" session={entry.binding.tmux_session}{ws}"
        print(f"- {entry.info.id} [{entry.process}] {entry.status.state} last={last}{binding}")
