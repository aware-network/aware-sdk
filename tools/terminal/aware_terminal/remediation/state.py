from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from aware_terminal.core.util import ensure_dirs
from .models import SetupState

DEFAULT_STATE_PATH = Path.home() / ".aware" / "terminal" / "setup_state.json"


def load_state(path: Optional[Path] = None) -> SetupState:
    target = path or DEFAULT_STATE_PATH
    if not target.exists():
        return SetupState()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return SetupState.model_validate(data)
    except Exception:
        return SetupState()


def save_state(state: SetupState, path: Optional[Path] = None) -> None:
    target = path or DEFAULT_STATE_PATH
    ensure_dirs([target.parent])
    payload = state.model_dump(mode="json")
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
