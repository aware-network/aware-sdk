from __future__ import annotations

import curses
from dataclasses import dataclass
from typing import Iterable, List

from ..models import ThreadDoc
from .components import safe_addnstr


@dataclass
class MarkdownView:
    """Scrollable markdown/text viewer for event documents."""

    doc: ThreadDoc
    offset: int = 0

    @property
    def lines(self) -> List[str]:
        return self.doc.content.splitlines() or [""]

    def reset(self) -> None:
        self.offset = 0

    def render(self, win, height: int, width: int, title: str) -> None:
        safe_addnstr(win, 0, 0, title.ljust(width), width, curses.color_pair(1) | curses.A_BOLD)
        visible_rows = max(0, height - 2)
        for idx in range(visible_rows):
            line_idx = self.offset + idx
            if line_idx >= len(self.lines):
                break
            safe_addnstr(win, 1 + idx, 0, self.lines[line_idx].ljust(width), width)
        footer = f"{self.offset + 1}-{min(self.offset + visible_rows, len(self.lines))} / {len(self.lines)}"
        safe_addnstr(win, height - 1, 0, footer.ljust(width), width, curses.A_DIM)

    def handle_key(self, key: int, viewport_height: int) -> bool:
        """Return True if the key exits the viewer."""
        visible_rows = max(0, viewport_height - 2)
        if key in (ord("q"), 27):
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            if self.offset + visible_rows < len(self.lines):
                self.offset += 1
        elif key in (curses.KEY_UP, ord("k")):
            if self.offset > 0:
                self.offset -= 1
        elif key == curses.KEY_NPAGE:
            self.offset = min(self.offset + visible_rows, max(0, len(self.lines) - visible_rows))
        elif key == curses.KEY_PPAGE:
            self.offset = max(self.offset - visible_rows, 0)
        return False
