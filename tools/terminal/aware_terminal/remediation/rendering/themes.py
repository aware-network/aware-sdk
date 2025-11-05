from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ActionTheme:
    icon: str
    color: str | None = None


@dataclass(frozen=True)
class RenderTheme:
    name: str
    actions: Dict[str, ActionTheme]
    default: ActionTheme
    success_color: str = "green"
    warning_color: str = "yellow"
    error_color: str = "red"
    info_color: str = "cyan"


DEFAULT_THEME = RenderTheme(
    name="default",
    actions={
        "manifest": ActionTheme(icon="[manifest]", color="cyan"),
        "tmux_service": ActionTheme(icon="[tmux]", color="blue"),
        "gnome_window": ActionTheme(icon="[gnome]", color="magenta"),
        "provider": ActionTheme(icon="[agent]", color="cyan"),
    },
    default=ActionTheme(icon="[setup]", color=None),
)


MINIMAL_THEME = RenderTheme(
    name="minimal",
    actions={},
    default=ActionTheme(icon="-", color=None),
    success_color="green",
    warning_color="yellow",
    error_color="red",
    info_color="cyan",
)
