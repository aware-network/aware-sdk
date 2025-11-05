from pathlib import Path

from aware_terminal.integrations.bindings import BindingStore, Binding, ThreadBinding


def test_binding_store_provider(tmp_path: Path) -> None:
    store = BindingStore(base=tmp_path)
    assert store.list() == {}
    store.set(Binding(provider="codex", session="aware", init="echo hi"))
    assert store.get("codex").session == "aware"
    store.remove("codex")
    assert store.get("codex") is None


def test_binding_store_threads(tmp_path: Path) -> None:
    store = BindingStore(base=tmp_path)
    thread_id = "desktop/thread-123"
    store.set_thread(ThreadBinding(thread_id=thread_id, tmux_session="aware", workspace=2))
    binding = store.get_thread(thread_id)
    assert binding and binding.tmux_session == "aware" and binding.workspace == 2
    store.remove_thread(thread_id)
    assert store.get_thread(thread_id) is None
