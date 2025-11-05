import json
from pathlib import Path

import pytest

from aware_environments.kernel.objects.agent import (
    create_process,
    create_thread,
    handlers,
)


def _write_role_registry(identities_root: Path, *, slugs: tuple[str, ...] = ("memory-baseline", "project-task-baseline")) -> Path:
    registry_path = identities_root / "_registry" / "role_registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": "2025-10-01T00:00:00Z",
        "roles": {
            slug: {
                "id": slug,
                "title": slug.replace("-", " ").title(),
                "policies": [],
                "cli": {"objects": {}},
            }
            for slug in slugs
        },
    }
    registry_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return registry_path


def _setup_agent_tree(tmp_path: Path) -> tuple[Path, dict]:
    identities_root = tmp_path / "docs" / "identities"
    payload = handlers.signup_handler(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
        is_main=True,
    )
    return identities_root, payload


def test_create_process_creates_metadata(tmp_path: Path) -> None:
    identities_root = tmp_path / "docs" / "identities"
    result = create_process(
        identities_root,
        agent_slug="demo-agent",
        process_slug="demo-process",
    )
    assert result.status == "created"
    assert result.process_path.exists()
    payload = result.payload
    assert payload["slug"] == "demo-process"


def test_create_thread_scaffolds_memory(tmp_path: Path) -> None:
    identities_root = tmp_path / "docs" / "identities"
    create_process(
        identities_root,
        agent_slug="demo-agent",
        process_slug="demo-process",
    )

    result = create_thread(
        identities_root,
        agent_slug="demo-agent",
        process_slug="demo-process",
        thread_slug="demo-thread",
        is_main=True,
    )

    assert result.thread_path.exists()
    hierarchy = result.hierarchy
    assert hierarchy["thread_data"]["name"] == "demo-thread"

    working_memory = (
        identities_root
        / "agents"
        / "demo-agent"
        / "runtime"
        / "process"
        / "demo-process"
        / "threads"
        / "demo-thread"
        / "working_memory.md"
    )
    assert working_memory.exists()


def test_handlers_signup(tmp_path: Path) -> None:
    identities_root, payload = _setup_agent_tree(tmp_path)
    thread_payload = payload["thread"]
    assert thread_payload["slug"] == "demo-thread"
    assert payload["process"]["status"] in {"created", "exists"}
    assert (identities_root / thread_payload["path"]).exists()


def test_handlers_list_agents(tmp_path: Path) -> None:
    identities_root = tmp_path / "docs" / "identities"
    agent_dir = identities_root / "agents" / "demo-agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agent.json").write_text(
        """{"id": "11111111-aaaa-bbbb-cccc-222222222222", "identity": {"public_key": "demo-agent"}}""",
        encoding="utf-8",
    )
    entries = handlers.list_agents(identities_root)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["slug"] == "demo-agent"
    assert entry["name"] == "demo-agent"


def test_handlers_whoami(tmp_path: Path) -> None:
    identities_root, _ = _setup_agent_tree(tmp_path)
    payload = handlers.whoami_handler(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
    )
    assert payload["agent"]["slug"] == "demo-agent"
    assert payload["process"]["slug"] == "demo-process"
    assert payload["thread"]["slug"] == "demo-thread"


def test_create_thread_handler_populates_roles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    identities_root = tmp_path / "docs" / "identities"
    _write_role_registry(identities_root)

    payload = handlers.create_thread_handler(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="analysis",
        is_main=True,
        role=("memory-baseline",),
    )

    assert payload["thread"] == "analysis"
    assert payload["roles"] == ["memory-baseline"]

    roles_path = identities_root / payload["roles_path"]
    assert roles_path.exists()
    roles_data = json.loads(roles_path.read_text(encoding="utf-8"))
    assert roles_data["agent"] == "demo-agent"
    assert roles_data["thread"] == "analysis"
    assert [entry["slug"] for entry in roles_data["roles"]] == ["memory-baseline"]

    guide_path = identities_root / payload["guide_path"]
    assert guide_path.exists()


def test_signup_handler_with_terminal_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    identities_root = tmp_path / "docs" / "identities"
    _write_role_registry(identities_root)

    captured: dict[str, object] = {}

    def _fake_login(
        identities_root_arg: Path,
        runtime_root: Path,
        aware_root: Path,
        *,
        agent: str,
        process: str,
        thread: str,
        provider: str,
        terminal_id: str,
        ensure_terminal: bool,
        allow_missing_session: bool,
    ):
        captured.update(
            {
                "identities_root": identities_root_arg,
                "runtime_root": runtime_root,
                "aware_root": aware_root,
                "agent": agent,
                "process": process,
                "thread": thread,
                "provider": provider,
                "terminal_id": terminal_id,
                "ensure_terminal": ensure_terminal,
                "allow_missing_session": allow_missing_session,
            }
        )
        return {
            "terminal_id": terminal_id,
            "provider": provider,
            "session": {"session_id": "provider-session"},
        }

    monkeypatch.setattr(handlers, "_agent_thread_login", _fake_login)

    payload = handlers.signup_handler(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
        provider="codex",
        with_terminal="term-main",
        allow_missing_session=True,
    )

    assert captured["provider"] == "codex"
    assert captured["terminal_id"] == "term-main"
    assert captured["ensure_terminal"] is True
    assert captured["allow_missing_session"] is True
    assert captured["runtime_root"]
    assert captured["aware_root"]

    terminal_payload = payload.get("terminal")
    assert terminal_payload and terminal_payload["terminal_id"] == "term-main"
    assert terminal_payload["session"]["session_id"] == "provider-session"
