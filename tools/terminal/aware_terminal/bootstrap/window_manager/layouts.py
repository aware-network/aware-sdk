from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from aware_terminal.core.config import ToolConfig
from aware_terminal.core.util import run


@dataclass
class WindowGeometry:
    x: int
    y: int
    width: int
    height: int


@dataclass
class WindowLayout:
    match: str
    workspace: Optional[int] = None
    geometry: Optional[WindowGeometry] = None
    desktop: Optional[str] = None


def _parse_geometry(payload: dict) -> Optional[WindowGeometry]:
    try:
        x = int(payload["x"])
        y = int(payload["y"])
        width = int(payload["width"])
        height = int(payload["height"])
    except (KeyError, ValueError, TypeError):
        return None
    return WindowGeometry(x=x, y=y, width=width, height=height)


def load_layout_manifest(path: Path) -> List[WindowLayout]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    items = data.get("layouts") if isinstance(data, dict) else None
    if not isinstance(items, Iterable):
        return []

    layouts: List[WindowLayout] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        match = item.get("match")
        if not isinstance(match, str) or not match:
            continue
        workspace = item.get("workspace")
        if isinstance(workspace, int) and workspace < 0:
            workspace = None
        geometry_payload = item.get("geometry")
        geometry = _parse_geometry(geometry_payload) if isinstance(geometry_payload, dict) else None
        desktop = item.get("desktop")
        layouts.append(WindowLayout(match=match, workspace=workspace, geometry=geometry, desktop=desktop))
    return layouts


def apply_layouts(cfg: ToolConfig, layouts: Iterable[WindowLayout]) -> dict:
    layouts = list(layouts)
    if not layouts:
        return {"status": "skipped", "message": "No layouts defined."}

    wmctrl = shutil.which("wmctrl")
    if not wmctrl:
        return {"status": "skipped", "message": "wmctrl not available on PATH."}

    applied = []
    for layout in layouts:
        extra: dict = {"match": layout.match}
        if layout.workspace is not None and layout.workspace > 0:
            target_ws = max(layout.workspace - 1, 0)
            run([wmctrl, "-x", "-r", layout.match, "-t", str(target_ws)], check=False)
            extra["workspace"] = layout.workspace
        if layout.geometry:
            geom = layout.geometry
            geometry_arg = f"0,{geom.x},{geom.y},{geom.width},{geom.height}"
            run([wmctrl, "-x", "-r", layout.match, "-e", geometry_arg], check=False)
            extra["geometry"] = geometry_arg
        applied.append(extra)

    return {"status": "applied", "count": len(applied), "details": applied}
