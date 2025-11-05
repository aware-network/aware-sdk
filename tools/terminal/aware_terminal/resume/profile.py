from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml

from ..core.config import SessionConfig, TerminalName


@dataclass
class Profile:
    name: Optional[str]
    terminal: Optional[TerminalName]
    sessions: List[SessionConfig]

    @staticmethod
    def load(path: Path) -> "Profile":
        text = path.read_text()
        try:
            if path.suffix.lower() in (".yaml", ".yml"):
                data = yaml.safe_load(text)
            else:
                data = json.loads(text)
        except Exception as exc:
            raise RuntimeError(f"Failed to parse profile {path}: {exc}")
        if not isinstance(data, dict):
            raise RuntimeError("Profile root must be a mapping")
        sessions = [SessionConfig(**item) for item in data.get("sessions", [])]
        return Profile(name=data.get("name"), terminal=data.get("terminal"), sessions=sessions)

    @staticmethod
    def template(name: str, terminal: TerminalName = "kitty", with_examples: bool = True) -> "Profile":
        sessions: List[SessionConfig] = []
        if with_examples:
            sessions = [
                SessionConfig(name="aware", workspace=1, cmd="cd ~/aware && bash", autostart=True, init=["echo 'aware session ready'"]),
                SessionConfig(name="agent", workspace=2, cmd="cd ~/aware/agents && bash", autostart=False),
            ]
        return Profile(name=name, terminal=terminal, sessions=sessions)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "terminal": self.terminal,
            "sessions": [s.model_dump() for s in self.sessions],
        }

    def save_yaml(self, path: Path) -> None:
        path.write_text(yaml.safe_dump(self.to_dict(), sort_keys=False))
