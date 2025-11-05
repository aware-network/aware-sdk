from pathlib import Path

from aware_environments.kernel.objects.agent_thread_memory import (
    AgentThreadFSAdapter,
    memory_append_episodic,
    memory_diff,
    memory_history,
    memory_status,
    memory_validate,
    memory_write_working,
)


def _thread_root(tmp_path: Path) -> Path:
    root = (
        tmp_path
        / "docs"
        / "identities"
        / "agents"
        / "demo-agent"
        / "runtime"
        / "process"
        / "demo-process"
        / "threads"
        / "demo-thread"
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_memory_write_and_status(tmp_path: Path) -> None:
    _thread_root(tmp_path)
    identities_root = tmp_path / "docs" / "identities"

    write_payload = memory_write_working(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
        content="Hello world",
    )
    assert write_payload["content"].strip() == "Hello world"
    receipts = write_payload.get("receipts")
    assert isinstance(receipts, list) and receipts
    assert receipts[0]["context"]["function"] == "write-working"

    summary = memory_status(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
        limit=5,
    )
    assert summary["working"]["content"].strip() == "Hello world"
    assert tuple(summary.get("rule_ids", ())) == ("04-agent-01-memory-hierarchy",)

    entry_payload = memory_append_episodic(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
        title="First",
        content="Entry",
        session_type="analysis",
    )
    assert entry_payload["body"].strip() == "Entry"
    entry_receipts = entry_payload.get("receipts")
    assert isinstance(entry_receipts, list) and entry_receipts
    assert entry_receipts[0]["context"]["function"] == "append-episodic"

    history_payload = memory_history(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
        limit=10,
    )
    assert tuple(history_payload.get("rule_ids", ())) == ("04-agent-01-memory-hierarchy",)
    history_entries = history_payload.get("entries")
    assert history_entries and history_entries[0]["body"].strip() == "Entry"

    diff_payload = memory_diff(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
        since="2000-01-01T00:00:00Z",
    )
    assert tuple(diff_payload.get("rule_ids", ())) == ("04-agent-01-memory-hierarchy",)
    assert diff_payload.get("events")

    validation = memory_validate(
        identities_root,
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
    )
    assert validation["working_exists"]
    assert validation["episodic_count"] == 1
    assert tuple(validation.get("rule_ids", ())) == ("04-agent-01-memory-hierarchy",)

    adapter = AgentThreadFSAdapter(identities_root)
    assert adapter.working_memory_path(
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
    ).exists()
    assert adapter.episodic_dir(
        agent="demo-agent",
        process="demo-process",
        thread="demo-thread",
    ).exists()
