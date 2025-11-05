from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aware_environments.kernel.objects.agent_thread import handlers as agent_thread_handlers
from aware_environments.kernel.objects import terminal as terminal_module


class _FakeRuntime:
    def __init__(self, tmp_path: Path) -> None:
        self._socket_dir = tmp_path / "sockets"
        self._socket_dir.mkdir(parents=True, exist_ok=True)

    def ensure_terminal_session(self, *, thread: str, terminal_id: str, cwd: Path, shell: str):
        socket_path = self._socket_dir / f"{terminal_id}.sock"
        socket_path.write_text("", encoding="utf-8")
        return SimpleNamespace(
            session_id=f"term-session-{terminal_id}",
            tmux_window=f"window-{terminal_id}",
            socket_path=socket_path,
        )

    def ensure_provider_session(
        self,
        *,
        thread: str,
        provider_slug: str,
        apt_id: str,
        resume: bool,
        existing_session_id: str | None,
        terminal_id: str | None,
    ):
        socket_path = self._socket_dir / f"provider-{terminal_id or 'default'}.sock"
        socket_path.write_text("", encoding="utf-8")
        return SimpleNamespace(
            session_id="provider-session",
            env={"AWARE_PROVIDER_SESSION_ID": "provider-session"},
            metadata={"version": "1.0.0", "channel": "stable"},
            socket_path=socket_path,
        )

    def discover_provider_session(
        self,
        thread_identifier: str,
        provider_slug: str,
        *,
        terminal_id: str | None = None,
        apt_id: str | None = None,
    ):
        return SimpleNamespace(
            success=True,
            message="ok",
            data={"session_id": "provider-session"},
        )


@pytest.fixture()
def agent_thread_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    identities_root = tmp_path / "docs" / "identities"
    runtime_root = tmp_path / "docs" / "runtime" / "process"
    aware_root = tmp_path / ".aware"

    identities_root.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)
    aware_root.mkdir(parents=True, exist_ok=True)

    fake_runtime = _FakeRuntime(tmp_path)
    monkeypatch.setattr(terminal_module.handlers, "_runtime_mod", fake_runtime)

    signup_payload = agent_thread_handlers.signup(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
        is_main=True,
    )

    return identities_root, runtime_root, aware_root, signup_payload


def test_agent_thread_signup_kernel_handler(agent_thread_env):
    identities_root, _runtime_root, _aware_root, signup_payload = agent_thread_env

    assert signup_payload["status"] == "created"
    thread_info = signup_payload["thread"]
    thread_path = identities_root / thread_info["path"]
    assert (thread_path / "agent_process_thread.json").exists()

    metadata = json.loads((thread_path / "agent_process_thread.json").read_text(encoding="utf-8"))
    assert metadata["name"] == "demo-thread"


def test_agent_thread_login_kernel_handler(agent_thread_env, monkeypatch: pytest.MonkeyPatch):
    identities_root, runtime_root, aware_root, _ = agent_thread_env

    payload = agent_thread_handlers.login(
        identities_root,
        runtime_root,
        aware_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
        provider="codex",
        terminal_id="term-main",
    )

    assert payload["session"]["session_id"] == "provider-session"
    assert payload["terminal_id"] == "term-main"
    receipts = payload.get("receipts")
    assert isinstance(receipts, list) and receipts, "Expected receipts from kernel login"
    assert any(entry.get("context", {}).get("function") == "bind-provider" for entry in receipts)
    journal = payload.get("journal")
    assert isinstance(journal, list) and journal, "Expected journal entries from kernel login"
    assert all(entry.get("action") == "apply-plan" for entry in journal)

    thread_doc_path = (
        identities_root
        / "agents"
        / "demo-agent"
        / "runtime"
        / "process"
        / "demo-process"
        / "threads"
        / "demo-thread"
        / "agent_process_thread.json"
    )
    thread_doc = json.loads(thread_doc_path.read_text(encoding="utf-8"))
    assert thread_doc.get("session_id") == "provider-session"
    assert thread_doc.get("metadata", {}).get("terminal_provider") == "codex"


def test_agent_thread_session_update_emits_receipt(agent_thread_env):
    identities_root, _runtime_root, _aware_root, _ = agent_thread_env

    result = agent_thread_handlers.session_update(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
        session_id="session-123",
        provider="codex",
        terminal_id="term-main",
        metadata_updates={"provider_session_id": "session-123"},
    )

    receipts = result.get("receipts")
    assert isinstance(receipts, list) and receipts, "Expected receipts from session update"
    assert receipts[0]["context"]["function"] == "session-update"
    journal = result.get("journal")
    assert isinstance(journal, list) and journal, "Expected journal entries from session update"
    assert journal[0]["action"] == "apply-plan"

    metadata_path = (
        identities_root
        / "agents"
        / "demo-agent"
        / "runtime"
        / "process"
        / "demo-process"
        / "threads"
        / "demo-thread"
        / "agent_process_thread.json"
    )
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert data["session_id"] == "session-123"
    assert data["metadata"]["terminal_provider"] == "codex"
    assert data["metadata"]["terminal_id"] == "term-main"
    assert data["metadata"]["provider_session_id"] == "session-123"
