from __future__ import annotations

from dataclasses import dataclass

from aware_terminal.core.config import ToolConfig
from aware_terminal.core.env import EnvironmentInspector


@dataclass(slots=True)
class DoctorContext:
    config: ToolConfig
    inspector: EnvironmentInspector
