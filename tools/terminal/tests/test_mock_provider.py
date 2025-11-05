import json
from pathlib import Path

from aware_terminal.control_center.mock_provider import MockControlDataProvider, DEFAULT_FIXTURES_DIR
from aware_terminal.control_center.view_model import ControlCenterViewModel
from aware_terminal.bindings import BindingStore


def make_provider(tmp_path: Path) -> MockControlDataProvider:
    state_path = tmp_path / "reviewed.json"
    return MockControlDataProvider(fixtures_dir=DEFAULT_FIXTURES_DIR, state_path=state_path)


def test_environments_and_processes(tmp_path: Path) -> None:
    provider = make_provider(tmp_path)

    environments = provider.list_environments()
    assert environments, "Expected at least one environment fixture"
    assert environments[0].slug == "aware-dev"

    processes = provider.list_processes(environments[0].id)
    assert processes, "Expected at least one process for environment"
    assert processes[0].slug == "terminal-session-management"


def test_threads_include_binding_hints(tmp_path: Path) -> None:
    provider = make_provider(tmp_path)
    view_model = ControlCenterViewModel(provider, binding_store=BindingStore(base=tmp_path))
    threads = view_model.refresh_threads()
    ids = {entry.info.id for entry in threads}
    assert "thread-control-center" in ids


def test_events_and_review_state(tmp_path: Path) -> None:
    provider = make_provider(tmp_path)
    events = provider.list_thread_events("thread-control-center")
    assert len(events) >= 2

    target = events[0]
    assert target.descriptor.channel in {"analysis", "design"}
    assert target.reviewed is False

    provider.mark_event_reviewed(target.id, True)
    refreshed = provider.list_thread_events("thread-control-center")
    updated = next(ev for ev in refreshed if ev.id == target.id)
    assert updated.reviewed is True

    state_file = tmp_path / "reviewed.json"
    assert json.loads(state_file.read_text()) == {target.id: True}


def test_fetch_doc(tmp_path: Path) -> None:
    provider = make_provider(tmp_path)
    event = provider.list_thread_events("thread-terminal-session")[0]
    doc = provider.get_event_doc(event.id)
    assert "Thread-Centric Resume UX" in doc.content
