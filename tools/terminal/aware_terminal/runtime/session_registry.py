from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional


def _state_path(path: Optional[Path] = None) -> Path:
    if path is not None:
        return path
    base = os.environ.get("AWARE_STATE_HOME")
    return (Path(base) if base else Path.home() / ".aware_state") / "terminal_sessions.json"


def _load_state(path: Optional[Path] = None) -> Dict[str, str]:
    path = _state_path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_state(state: Dict[str, str], path: Optional[Path] = None) -> None:
    path = _state_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_last_session(thread: str, *, state_path: Optional[Path] = None) -> Optional[str]:
    return _load_state(state_path).get(thread)


def set_last_session(thread: str, session_id: str, *, state_path: Optional[Path] = None) -> None:
    state = _load_state(state_path)
    state[thread] = session_id
    _write_state(state, state_path)


def clear_last_session(thread: str, *, state_path: Optional[Path] = None) -> None:
    state = _load_state(state_path)
    if thread in state:
        del state[thread]
        _write_state(state, state_path)
