from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest

from aware_terminal.runtime import session as session_module
from aware_terminal.providers.base import (
    ProviderActionResult,
    ProviderContext,
    ProviderSessionResult,
    TerminalProvider,
    TerminalProviderInfo,
)


class StubProvider(TerminalProvider):
    def __init__(self) -> None:
        super().__init__(
            TerminalProviderInfo(
                slug="codex",
                title="Stub Codex",
                description="stub",
            )
        )

    def install(self) -> ProviderActionResult:
        return ProviderActionResult(success=True, message="install-ok")

    def update(self) -> ProviderActionResult:
        return ProviderActionResult(success=True, message="update-ok")

    def resume(
        self,
        *,
        session_id: Optional[str] = None,
        context: Optional[ProviderContext] = None,
    ) -> ProviderSessionResult:
        return session_module.ProviderSessionResult(
            session_id=session_id or "stub-session",
            command=["echo", "resume"],
            cwd=None,
            env=None,
            metadata={"stub": True},
        )

    def launch(
        self,
        *,
        resume: bool = False,
        context: Optional[ProviderContext] = None,
    ) -> ProviderSessionResult:
        return session_module.ProviderSessionResult(
            session_id="stub-launch",
            command=["echo", "launch"],
            cwd=None,
            env=None,
            metadata={"stub": True},
        )

    def resolve_active_session(
        self,
        *,
        context: Optional[ProviderContext] = None,
    ) -> ProviderActionResult:
        payload = {
            "provider": self.info.slug,
            "session_id": "stub-session",
            "env": {"AWARE_PROVIDER_SESSION_ID": "stub-session"},
            "resolution": {"source": "stub"},
        }
        if context and context.thread_id:
            payload["thread_id"] = context.thread_id
        if context and context.terminal_id:
            payload["terminal_id"] = context.terminal_id
        if context and context.apt_id:
            payload["apt_id"] = context.apt_id
        return ProviderActionResult(success=True, message="detected", data=payload)


class DummySessionManager:
    def __init__(self, *, thread, manifest_store, socket_path):
        self.thread = thread
        self.manifest_store = manifest_store
        self.socket_path = socket_path

    def register_session(self, session_id, shell, cwd, *, terminal_id=None, apt_id=None, tmux_window=None,
                         start_script=None, provider=None, command=None, env=None):
        return SimpleNamespace(
            session_id=session_id,
            tmux_window=tmux_window or (f"term-{terminal_id}" if terminal_id else session_id),
            terminal_id=terminal_id,
            apt_id=apt_id,
            provider=provider,
        )


@pytest.fixture(autouse=True)
def patch_session_manager(monkeypatch):
    monkeypatch.setattr(session_module, "SessionManager", DummySessionManager)


def test_ensure_terminal_session_writes_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AWARE_HOME", str(tmp_path / "aware"))
    monkeypatch.setenv("AWARE_RUNTIME_DIR", str(tmp_path / "runtime"))

    thread_id = "process/main"
    result = session_module.ensure_terminal_session(thread_id, "term-alpha", cwd=tmp_path / "workspace")

    sessions_dir = tmp_path / "aware" / "sessions"
    receipt_path = sessions_dir / "term-alpha.json"
    assert receipt_path.exists()

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["session_id"] == "term-alpha"
    assert receipt["thread_id"] == thread_id
    assert receipt["status"] == "running"
    assert receipt["descriptor_path"].endswith("terminals/term-alpha.json")

    current_path = sessions_dir / "current_session.json"
    assert current_path.exists()
    current = json.loads(current_path.read_text(encoding="utf-8"))
    assert current["session_id"] == "term-alpha"

    session_module.mark_session_status(thread_id, "term-alpha", "stopped", reason="test")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "stopped"
    assert receipt["reason"] == "test"
    assert not current_path.exists()


def test_mark_session_status_no_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AWARE_HOME", str(tmp_path / "aware"))
    session_module.mark_session_status("process/main", "missing-session", "stopped")
    # nothing should explode and no files created
    assert not (tmp_path / "aware").exists()


def test_discover_provider_session_persists_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AWARE_HOME", str(tmp_path / "aware"))
    provider = StubProvider()

    monkeypatch.setattr(session_module, "get_provider", lambda slug: provider if slug == "codex" else None)

    result = session_module.discover_provider_session(
        "process/main",
        "codex",
        terminal_id="term-beta",
        apt_id="apt-9",
    )

    assert result.success
    assert result.data is not None
    assert result.data["session_id"] == "stub-session"
    assert result.data["provider"] == "codex"
    assert result.data["env"]["AWARE_PROVIDER_SESSION_ID"] == "stub-session"

    sessions_dir = tmp_path / "aware" / "sessions"
    receipt_path = sessions_dir / "stub-session.json"
    assert receipt_path.exists()
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["thread_id"] == "process/main"
    assert payload["terminal_id"] == "term-beta"
    assert payload["apt_id"] == "apt-9"
    assert payload["provider"] == "codex"
    assert payload["env"]["AWARE_PROVIDER_SESSION_ID"] == "stub-session"

    current_path = sessions_dir / "current_session.json"
    assert current_path.exists()
    pointer = json.loads(current_path.read_text(encoding="utf-8"))
    assert pointer["session_id"] == "stub-session"
