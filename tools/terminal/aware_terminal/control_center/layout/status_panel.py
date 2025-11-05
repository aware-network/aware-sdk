from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from ..view_model import ThreadContext
from ..models import ThreadEvent
from ...core.util import human_ago


def build_status_line(selected: Optional[ThreadContext], events: Sequence[ThreadEvent]) -> str:
    if not selected:
        return "No thread selected"
    session = selected.binding.tmux_session if selected.binding else "-"
    workspace = (
        f"/{selected.binding.workspace}" if selected.binding and selected.binding.workspace is not None else ""
    )
    last = selected.status.last_event_timestamp
    ago = human_ago(int((datetime.now(timezone.utc) - last).total_seconds())) if last else "--"
    unreviewed = sum(1 for ev in events if not ev.reviewed)
    return (
        f"{selected.info.name} [{selected.process}] "
        f"state={selected.status.state} "
        f"binding={session}{workspace} "
        f"last={ago} "
        f"unreviewed={unreviewed}"
    )
