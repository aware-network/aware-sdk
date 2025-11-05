from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


@dataclass
class Binding:
    provider: str
    session: str
    init: Optional[str] = None


@dataclass
class ThreadBinding:
    thread_id: str
    tmux_session: str
    workspace: Optional[int] = None


class BindingStore:
    def __init__(self, base: Optional[Path] = None) -> None:
        self.base = base or (Path.home() / ".aware" / "terminal")
        self.base.mkdir(parents=True, exist_ok=True)
        self.path = self.base / "bindings.json"
        self._data: Dict[str, Dict[str, Dict[str, str]]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text())
                if "providers" in raw or "threads" in raw:
                    self._data = {"providers": raw.get("providers", {}), "threads": raw.get("threads", {})}
                else:
                    self._data = {"providers": raw, "threads": {}}
            except Exception:
                self._data = {"providers": {}, "threads": {}}
        else:
            self._data = {"providers": {}, "threads": {}}

    def _write(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))

    def list(self) -> Dict[str, Dict[str, str]]:
        return dict(self._data.get("providers", {}))

    def list_threads(self) -> Dict[str, Dict[str, str]]:
        return dict(self._data.get("threads", {}))

    def get(self, provider: str) -> Optional[Binding]:
        raw = self._data.get("providers", {}).get(provider)
        if not raw:
            return None
        return Binding(provider=provider, session=raw.get("session", ""), init=raw.get("init"))

    def set(self, b: Binding) -> None:
        providers = self._data.setdefault("providers", {})
        providers[b.provider] = {"session": b.session, "init": b.init or ""}
        self._write()

    def remove(self, provider: str) -> bool:
        providers = self._data.setdefault("providers", {})
        if provider in providers:
            del providers[provider]
            self._write()
            return True
        return False

    # Thread bindings ----------------------------------------------------------------------
    def get_thread(self, thread_id: str) -> Optional[ThreadBinding]:
        raw = self._data.get("threads", {}).get(thread_id)
        if not raw:
            return None
        return ThreadBinding(
            thread_id=thread_id,
            tmux_session=raw.get("session", ""),
            workspace=raw.get("workspace"),
        )

    def set_thread(self, binding: ThreadBinding) -> None:
        threads = self._data.setdefault("threads", {})
        payload = {"session": binding.tmux_session}
        if binding.workspace is not None:
            payload["workspace"] = binding.workspace
        threads[binding.thread_id] = payload
        self._write()

    def remove_thread(self, thread_id: str) -> bool:
        threads = self._data.setdefault("threads", {})
        if thread_id in threads:
            del threads[thread_id]
            self._write()
            return True
        return False
