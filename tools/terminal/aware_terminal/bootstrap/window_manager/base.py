from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass
class WindowPlacementResult:
    status: str  # success | manual | failed
    summary: str
    command: Optional[List[str]] = None
    message: Optional[str] = None
    data: Optional[dict] = None


class WindowPlacementManager(Protocol):
    def capabilities(self) -> dict:
        ...

    def ensure_ready(self, auto: bool) -> WindowPlacementResult:
        ...

    def describe(self) -> str:
        ...
