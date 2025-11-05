from pathlib import Path

from aware_environments.kernel.objects.agent_thread.handlers import session_update


def _write_metadata(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(__import__("json").dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_session_update(tmp_path: Path) -> None:
    identities_root = tmp_path / "docs" / "identities"
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
    _write_metadata(
        metadata_path,
        {
            "id": "apt-1",
            "metadata": {"terminal_provider": "existing"},
        },
    )

    payload = session_update(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
        session_id="session-123",
        provider="provider-a",
        terminal_id="term-1",
        metadata_updates={"transport": "ssh"},
    )

    assert payload["session_id"] == "session-123"
    receipts = payload.get("receipts")
    assert isinstance(receipts, list) and receipts
    assert receipts[0]["context"]["function"] == "session-update"
    journal = payload.get("journal")
    assert isinstance(journal, list) and journal
    assert journal[0]["action"] == "apply-plan"

    updated = __import__("json").loads(metadata_path.read_text(encoding="utf-8"))
    assert updated["session_id"] == "session-123"
    assert updated["metadata"]["terminal_provider"] == "provider-a"
    assert updated["metadata"]["terminal_id"] == "term-1"
    assert updated["metadata"]["transport"] == "ssh"
