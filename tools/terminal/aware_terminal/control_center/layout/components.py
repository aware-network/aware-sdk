from __future__ import annotations

import curses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

from ..view_model import ThreadContext
from ..models import ThreadEvent
from ...core.util import human_ago


@dataclass(frozen=True)
class PaneDimensions:
    y: int
    x: int
    height: int
    width: int


def safe_addnstr(win, y: int, x: int, text: str, width: int, attr: int = 0) -> None:
    """Guarded wrapper that avoids raising `curses.error` during tight layouts."""
    if width <= 0:
        return
    try:
        win.addnstr(y, x, text, width, attr)
    except curses.error:
        pass


def draw_header(win, width: int, environment_name: str, filter_text: str) -> None:
    title = f"Control Center — Environment: {environment_name}"
    safe_addnstr(win, 0, 0, title.ljust(width), width, curses.color_pair(1) | curses.A_BOLD)
    help_line = (
        "Enter attach | b bind | v view doc | m toggle reviewed | r refresh | "
        "R refresh all | / filter | d doc pane | t stream | q quit"
    )
    safe_addnstr(win, 1, 0, help_line.ljust(width), width, curses.A_DIM)
    filter_line = f"Filter threads: {filter_text}"
    safe_addnstr(win, 2, 0, filter_line.ljust(width), width, curses.A_DIM)


def draw_threads_list(
    win,
    dims: PaneDimensions,
    threads: Sequence[ThreadContext],
    selected_index: int,
    now: Optional[datetime] = None,
) -> None:
    safe_addnstr(win, dims.y, dims.x, "Threads".ljust(dims.width), dims.width, curses.A_UNDERLINE)
    if not threads:
        placeholder = "No threads found"
        safe_addnstr(win, dims.y + 1, dims.x, placeholder.ljust(dims.width), dims.width, curses.A_DIM)
        return

    now_dt = now or datetime.now(timezone.utc)
    max_rows = max(0, dims.height - 1)
    for idx, entry in enumerate(threads[:max_rows]):
        row = dims.y + 1 + idx
        last_ts = entry.status.last_event_timestamp
        ago = human_ago(int((now_dt - last_ts).total_seconds())) if last_ts else "--"
        session = entry.binding.tmux_session if entry.binding else "-"
        workspace = f"/{entry.binding.workspace}" if entry.binding and entry.binding.workspace is not None else ""
        icon = "🔗" if entry.binding and entry.binding.tmux_session else "⛔"
        status = entry.status.state.upper()
        line = (
            f"{icon} {entry.info.name:<28.28} [{entry.process:<18.18}] "
            f"{status:<8} {ago:>8} {session}{workspace}"
        )
        attr = curses.A_REVERSE if idx == selected_index else curses.A_NORMAL
        if entry.status.state == "active":
            attr |= curses.color_pair(2)
        elif entry.status.state == "waiting":
            attr |= curses.color_pair(3)
        safe_addnstr(win, row, dims.x, line.ljust(dims.width), dims.width, attr)


def draw_events_list(
    win,
    dims: PaneDimensions,
    events: Sequence[ThreadEvent],
    selected_index: int,
) -> None:
    safe_addnstr(win, dims.y, dims.x, "Events".ljust(dims.width), dims.width, curses.A_UNDERLINE)
    if not events:
        placeholder = "No events for thread"
        safe_addnstr(win, dims.y + 1, dims.x, placeholder.ljust(dims.width), dims.width, curses.A_DIM)
        return

    max_rows = max(0, dims.height - 1)
    for idx, event in enumerate(events[:max_rows]):
        row = dims.y + 1 + idx
        reviewed_flag = "✓" if event.reviewed else "✗"
        label = event.descriptor.label or event.descriptor.channel
        line = (
            f"[{reviewed_flag}] {event.timestamp.isoformat()} "
            f"{event.change_type:<10.10} {label}"
        )
        attr = curses.A_REVERSE if idx == selected_index else curses.A_NORMAL
        safe_addnstr(win, row, dims.x, line.ljust(dims.width), dims.width, attr)


def draw_footer(win, row: int, width: int, message: str) -> None:
    safe_addnstr(win, row, 0, message.ljust(width), width, curses.A_DIM)
