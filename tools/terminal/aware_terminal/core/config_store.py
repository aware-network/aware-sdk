from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .config import TerminalBackend, TerminalName


class ConfigStore:
    """Persist lightweight user preferences under ~/.aware/terminal.

    Layout:
      ~/.aware/terminal/config.json
      ~/.aware/terminal/profiles/
    """

    def __init__(self, base: Optional[Path] = None) -> None:
        self.base = base or (Path.home() / ".aware" / "terminal")
        self.base.mkdir(parents=True, exist_ok=True)
        self.config_path = self.base / "config.json"
        self.profiles_dir = self.base / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def read(self) -> dict:
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text())
            except Exception:
                return {}
        return {}

    def write(self, data: dict) -> None:
        self.config_path.write_text(json.dumps(data, indent=2))

    def get_default_terminal(self) -> Optional[TerminalBackend]:
        data = self.read()
        name = data.get("default_terminal")
        if name in ("wezterm", "kitty", "alacritty", "gnome-terminal"):
            return TerminalBackend.from_name(name)  # type: ignore[arg-type]
        return None

    def set_default_terminal(self, name: TerminalName) -> None:
        data = self.read()
        data["default_terminal"] = name
        self.write(data)

    def get_launch_on_add(self) -> bool:
        data = self.read()
        val = data.get("launch_on_add")
        return bool(val) if val is not None else False

    def set_launch_on_add(self, value: bool) -> None:
        data = self.read()
        data["launch_on_add"] = bool(value)
        self.write(data)

    def get_resume_default(self) -> str:
        data = self.read()
        val = data.get("resume_default")
        return val if val in ("launch", "attach") else "launch"

    def set_resume_default(self, value: str) -> None:
        if value not in ("launch", "attach"):
            raise ValueError("resume_default must be 'launch' or 'attach'")
        data = self.read()
        data["resume_default"] = value
        self.write(data)
