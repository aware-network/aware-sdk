from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict

from ..core.config import ToolConfig


Action = Dict[str, Optional[str]]


@dataclass
class ResumeResult:
    action: str = "none"
    name: Optional[str] = None


def run_resume_tui(cfg: ToolConfig) -> Action:
    # Legacy resume interface: inform users to use Control Center.
    print("Legacy resume interface is deprecated. Use `aware-terminal control` instead.")
    return {"action": "none", "name": None}
