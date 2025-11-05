from __future__ import annotations

import os
from pathlib import Path

from .util import run, which


class EnvironmentInspector:
    def session_type(self) -> str:
        t = os.environ.get("XDG_SESSION_TYPE")
        if t:
            return t
        res = run(["bash", "-lc", "echo ${XDG_SESSION_TYPE:-unknown}"])
        return res.out.strip() or "unknown"

    def has_gnome(self) -> bool:
        # Rough check: gsettings exists and GNOME schema is present
        if which("gsettings") is None:
            return False
        res = run(["bash", "-lc", "gsettings list-schemas | grep -q org.gnome.shell && echo yes || echo no"])
        return res.out.strip() == "yes"

    def ensure_path(self, p: Path) -> None:
        p.mkdir(parents=True, exist_ok=True)

    def user(self) -> str:
        res = run(["bash", "-lc", "id -un"])
        return res.out.strip()
