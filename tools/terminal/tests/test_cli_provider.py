from pathlib import Path

from aware_terminal.control_center.provider import CliControlDataProvider
from aware_terminal.control_center.view_model import ControlCenterViewModel
from aware_terminal.integrations.bindings import BindingStore


class StubCliProvider(CliControlDataProvider):
    def __init__(self) -> None:
        super().__init__(runtime_root=Path("docs/runtime/process"))
        self._responses = {
            "thread-list": [
                {
                    "id": "desktop/thread-control",
                    "uuid": "thread-1",
                    "process_slug": "desktop",
                    "thread_slug": "thread-control",
                    "title": "Control",
                    "is_main": True,
                    "path": str(Path.cwd() / "docs/runtime/process/desktop/threads/thread-control"),
                },
                {
                    "id": "agent/thread-other",
                    "process_slug": "agent",
                    "thread_slug": "thread-other",
                    "title": "Other",
                    "is_main": False,
                    "path": str(Path.cwd() / "docs/runtime/process/agent/threads/thread-other"),
                },
            ],
            "status:desktop/thread-control": {
                "id": "desktop/thread-control",
                "title": "Control",
                "path": str(Path.cwd() / "docs/runtime/process/desktop/threads/thread-control"),
                "branches": [
                    {
                        "pane_kind": "analysis",
                        "name": "Analysis",
                        "branch_path": "branches/analysis.json",
                        "updated_at": "2025-10-12T20:13:19Z",
                        "pane_manifest": {"payload": {"doc": "analysis/doc.md"}},
                    }
                ],
            },
            "status:agent/thread-other": {
                "id": "agent/thread-other",
                "title": "Other",
                "path": str(Path.cwd() / "docs/runtime/process/agent/threads/thread-other"),
                "branches": [],
            },
        }

    def _run_cli_json(self, args):  # type: ignore[override]
        if args[:4] == ["object", "list", "--type", "thread"]:
            return self._responses["thread-list"]
        if args[:6] == ["object", "call", "--type", "thread", "--id", "desktop/thread-control"]:
            return self._responses["status:desktop/thread-control"]
        if args[:6] == ["object", "call", "--type", "thread", "--id", "agent/thread-other"]:
            return self._responses["status:agent/thread-other"]
        raise AssertionError(f"Unexpected args: {args}")


def test_cli_provider_status_and_events(tmp_path: Path) -> None:
    provider = StubCliProvider()
    view_model = ControlCenterViewModel(provider, binding_store=BindingStore(base=tmp_path))

    threads = view_model.refresh_threads(force=True)
    thread = next(ctx for ctx in threads if ctx.info.slug == "thread-control")

    events = view_model.load_events(thread.info.id)
    assert len(events) == 1
    doc = view_model.get_event_doc(events[0].id)
    assert isinstance(doc.content, str)
