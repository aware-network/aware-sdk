from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from aware_environment.fs import apply_plan
from aware_environments.kernel.objects.terminal import handlers as terminal_handlers


class _FakeRuntime:
    def __init__(self, tmp_path: Path) -> None:
        self._socket_path = tmp_path / "runtime.sock"

    # create_terminal uses this helper
    def ensure_terminal_session(self, *, thread: str, terminal_id: str, cwd: Path, shell: str):  # noqa: D401
        return SimpleNamespace(
            session_id="terminal-session",
            tmux_window="win-1",
            socket_path=self._socket_path,
        )

    # bind_provider uses this helper
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
        return SimpleNamespace(
            session_id="provider-session",
            env={"KEY": "VALUE"},
            metadata={"version": "1.0.0", "channel": "stable"},
            socket_path=self._socket_path,
        )

    # session_resolve uses this helper
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
def runtime_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runtime_root = tmp_path / "runtime"
    aware_root = tmp_path / "aware"
    identities_root = tmp_path / "identities"

    thread_dir = runtime_root / "demo-process" / "threads" / "main"
    thread_dir.mkdir(parents=True, exist_ok=True)
    thread_payload = {
        "id": str(uuid.uuid4()),
        "process_id": str(uuid.uuid4()),
        "title": "Demo Thread",
        "description": "",
        "is_main": True,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    (thread_dir / "thread.json").write_text(json.dumps(thread_payload) + "\n", encoding="utf-8")

    aware_root.mkdir(parents=True, exist_ok=True)

    fake_runtime = _FakeRuntime(tmp_path)
    monkeypatch.setattr(terminal_handlers, "_runtime_mod", fake_runtime)

    return runtime_root, aware_root, identities_root


def _write_participants_manifest(manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_payload = {
        "version": 1,
        "thread_id": "demo-process/main",
        "process_slug": "demo-process",
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "participants": [
            {
                "participant_id": "agent-apt",
                "type": "agent",
                "role": "executor",
                "status": "attached",
                "identity": {
                    "type": "agent",
                    "agent_process_thread_id": str(uuid.uuid4()),
                    "agent_process_id": str(uuid.uuid4()),
                    "agent_id": str(uuid.uuid4()),
                    "identity_id": str(uuid.uuid4()),
                    "actor_id": str(uuid.uuid4()),
                    "slug": "demo-agent/demo-process/main",
                },
                "last_seen": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "session": {"state": "unknown", "session_id": None},
                "metadata": {},
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")


def test_create_terminal_kernel_handler(runtime_env):
    runtime_root, aware_root, identities_root = runtime_env

    result = terminal_handlers.create_terminal(
        runtime_root,
        aware_root,
        thread_identifier="demo-process/main",
    )

    if hasattr(result, "plans"):
        for plan in getattr(result, "plans", ()):  # apply descriptor/pane writes
            apply_plan(plan)
        payload = getattr(result, "payload", {})
    else:
        payload = result

    thread_data = json.loads((runtime_root / "demo-process" / "threads" / "main" / "thread.json").read_text())

    terminal = payload["terminal"]
    assert terminal["thread_id"] == thread_data["id"]
    assert payload["session"]["session_id"] == "terminal-session"

    descriptor_path = Path(payload["descriptor_path"])
    assert descriptor_path.exists()


def test_session_resolve_kernel_handler(runtime_env):
    runtime_root, aware_root, identities_root = runtime_env

    payload = terminal_handlers.session_resolve(
        runtime_root,
        aware_root,
        identities_root,
        thread_identifier="demo-process/main",
        provider="codex",
    )

    assert payload["success"] is True
    assert payload["provider"] == "codex"


def test_list_terminals_kernel_handler_returns_serializable_payload(runtime_env):
    runtime_root, aware_root, identities_root = runtime_env

    create_result = terminal_handlers.create_terminal(
        runtime_root,
        aware_root,
        thread_identifier="demo-process/main",
        terminal_id="term-main",
    )

    if hasattr(create_result, "plans"):
        for plan in getattr(create_result, "plans", ()):
            apply_plan(plan)

    payload = terminal_handlers.list_terminals(
        runtime_root,
        aware_root,
        thread_identifier="demo-process/main",
    )

    # Should be JSON serialisable to support receipts.
    json.dumps(payload)

    assert payload["count"] == 1
    entry = payload["terminals"][0]
    assert entry["id"] == "term-main"
    assert entry["descriptor_path"].endswith("term-main.json")
    assert entry["socket_path"] is None or isinstance(entry["socket_path"], str)


def test_bind_provider_kernel_handler(runtime_env, tmp_path: Path):
    runtime_root, aware_root, identities_root = runtime_env

    create_result = terminal_handlers.create_terminal(
        runtime_root,
        aware_root,
        thread_identifier="demo-process/main",
        terminal_id="term-main",
    )

    if hasattr(create_result, "plans"):
        for plan in getattr(create_result, "plans", ()):  # apply descriptor/pane writes
            apply_plan(plan)
        create_payload = getattr(create_result, "payload", {})
    else:
        create_payload = create_result

    descriptor_path = Path(create_payload["descriptor_path"])
    assert descriptor_path.exists()

    manifest_path = runtime_root / "demo-process" / "threads" / "main" / "participants.json"
    _write_participants_manifest(manifest_path)

    thread_identity_dir = (
        identities_root / "agents" / "demo-agent" / "runtime" / "process" / "demo-process" / "threads" / "main"
    )
    thread_identity_dir.mkdir(parents=True, exist_ok=True)
    (thread_identity_dir / "agent_process_thread.json").write_text("{}\n", encoding="utf-8")

    bind_result = terminal_handlers.bind_provider(
        runtime_root,
        aware_root,
        identities_root,
        thread_identifier="demo-process/main",
        terminal_id="term-main",
        apt_id="agent-apt",
        provider="codex",
        metadata={"provider_session_id": "provider-session"},
    )

    if hasattr(bind_result, "plans"):
        for plan in getattr(bind_result, "plans", ()):  # apply descriptor/manifests
            apply_plan(plan)
        payload = getattr(bind_result, "payload", {})
    else:
        payload = bind_result

    assert payload["provider"] == "codex"
    assert payload["session_id"] == "provider-session"

    descriptor_data = json.loads(descriptor_path.read_text(encoding="utf-8"))
    assert descriptor_data["provider"]["slug"] == "codex"
    assert descriptor_data["metadata"]["provider_session_id"] == "provider-session"

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["participants"][0]["session"]["session_id"] == "provider-session"

    metadata_path = thread_identity_dir / "agent_process_thread.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata.get("session_id") == "provider-session"


def test_ensure_terminal_session_payload_is_serialisable(runtime_env, tmp_path: Path):
    runtime_root, aware_root, identities_root = runtime_env

    create_result = terminal_handlers.create_terminal(
        runtime_root,
        aware_root,
        thread_identifier="demo-process/main",
        terminal_id="term-main",
    )

    if hasattr(create_result, "plans"):
        for plan in getattr(create_result, "plans", ()):
            apply_plan(plan)

    manifest_path = runtime_root / "demo-process" / "threads" / "main" / "participants.json"
    _write_participants_manifest(manifest_path)

    thread_identity_dir = (
        identities_root / "agents" / "demo-agent" / "runtime" / "process" / "demo-process" / "threads" / "main"
    )
    thread_identity_dir.mkdir(parents=True, exist_ok=True)
    (thread_identity_dir / "agent_process_thread.json").write_text("{}\n", encoding="utf-8")

    ensure_result = terminal_handlers.ensure_terminal_session(
        runtime_root,
        aware_root,
        identities_root,
        thread_identifier="demo-process/main",
        apt_id="agent-apt",
        provider="codex",
        resume=False,
        metadata={"attempt": 1},
        terminal_id="term-main",
    )

    assert hasattr(ensure_result, "plans"), "ensure_terminal_session should return a TerminalPlanResult"
    for plan in getattr(ensure_result, "plans", ()):
        apply_plan(plan)
    payload = getattr(ensure_result, "payload", {})

    # Payload must be JSON serialisable for executor responses.
    json.dumps(payload)

    assert payload["provider"] == "codex"
    assert payload["terminal_id"] == "term-main"
    assert payload["metadata"]["provider"] == "codex"
    # metadata values should be strings
    assert payload["metadata"]["attempt"] == "1"

def test_delete_terminal_kernel_handler(runtime_env, tmp_path: Path):
    runtime_root, aware_root, identities_root = runtime_env

    create_result = terminal_handlers.create_terminal(
        runtime_root,
        aware_root,
        thread_identifier="demo-process/main",
        terminal_id="term-main",
    )

    if hasattr(create_result, "plans"):
        for plan in getattr(create_result, "plans", ()):
            apply_plan(plan)
        create_payload = getattr(create_result, "payload", {})
    else:
        create_payload = create_result

    descriptor_path = Path(create_payload["descriptor_path"])
    assert descriptor_path.exists()
    descriptor_data = json.loads(descriptor_path.read_text(encoding="utf-8"))

    # Seed participants manifest with an attached agent using the session created above.
    manifest_path = runtime_root / "demo-process" / "threads" / "main" / "participants.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "thread_id": "demo-process/main",
                "process_slug": "demo-process",
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "participants": [
                    {
                        "participant_id": "agent-apt",
                        "type": "agent",
                        "role": "executor",
                        "status": "attached",
                        "identity": {
                            "type": "agent",
                            "agent_process_thread_id": str(uuid.uuid4()),
                            "agent_process_id": str(uuid.uuid4()),
                            "agent_id": str(uuid.uuid4()),
                            "identity_id": str(uuid.uuid4()),
                            "actor_id": str(uuid.uuid4()),
                            "slug": "demo-agent/demo-process/main",
                        },
                        "last_seen": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "session": {
                            "state": "running",
                            "session_id": descriptor_data["session_id"],
                        },
                        "metadata": {},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    delete_result = terminal_handlers.delete_terminal(
        runtime_root,
        aware_root,
        thread_identifier="demo-process/main",
        terminal_id="term-main",
        remove_session=True,
    )

    assert hasattr(delete_result, "plans"), "Kernel delete should return a TerminalPlanResult"
    for plan in getattr(delete_result, "plans", ()):
        apply_plan(plan)
    payload = getattr(delete_result, "payload", {})

    # Descriptor is archived and removed from original location.
    archive_path = Path(payload["descriptor_archive_path"])
    assert archive_path.parent.name == ".deleted"
    assert archive_path.exists()
    assert not descriptor_path.exists()

    # Participants manifest is updated to detach the agent session.
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    participant_entry = manifest_data["participants"][0]
    assert participant_entry["status"] == "detached"
    assert participant_entry["session"] is None

    # Payload exposes session metadata for receipt generation.
    assert payload["thread_id"] == descriptor_data["thread_id"]
    assert payload["terminal_id"] == "term-main"
    assert payload["session_id"] == descriptor_data["session_id"]
    assert payload["kill_window"] is False
