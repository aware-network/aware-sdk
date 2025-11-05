from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, List

from pydantic import BaseModel, Field


TerminalName = Literal["wezterm", "kitty", "alacritty", "gnome-terminal"]


class TerminalBackend(BaseModel):
    name: TerminalName = Field(default="kitty")
    exec: str = Field(default="kitty")

    @classmethod
    def from_name(cls, name: TerminalName) -> "TerminalBackend":
        defaults = {
            "wezterm": "wezterm",
            "kitty": "kitty",
            "alacritty": "alacritty",
            "gnome-terminal": "gnome-terminal",
        }
        return cls(name=name, exec=defaults[name])


class SessionConfig(BaseModel):
    name: str
    workspace: int
    cmd: Optional[str] = None
    autostart: bool = False
    init: Optional[List[str]] = None


class ToolConfig(BaseModel):
    default_terminal: TerminalBackend = Field(default_factory=TerminalBackend)
    tmux_conf_path: Path = Field(default=Path.home() / ".tmux.conf")
    tmux_dir: Path = Field(default=Path.home() / ".tmux")
    plugins_dir: Path = Field(default=Path.home() / ".tmux" / "plugins")
    resurrect_dir: Path = Field(default=Path.home() / ".tmux" / "resurrect")
    systemd_user_dir: Path = Field(default=Path.home() / ".config" / "systemd" / "user")
    applications_dir: Path = Field(default=Path.home() / ".local" / "share" / "applications")
    autostart_dir: Path = Field(default=Path.home() / ".config" / "autostart")
    window_rules_path: Path = Field(default=Path.home() / ".aware" / "window_rules.json")
    window_layout_path: Path = Field(default=Path.home() / ".aware" / "terminal" / "window_layouts.json")
