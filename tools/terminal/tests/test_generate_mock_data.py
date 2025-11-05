import argparse
import importlib
import json
from pathlib import Path


def test_generate_mock_data(tmp_path: Path, monkeypatch) -> None:
    module = importlib.import_module("aware_terminal.mock_data.generate")

    repo_root = tmp_path / "repo"
    docs_root = repo_root / "docs" / "projects" / "demo" / "tasks" / "task-one"
    analysis_dir = docs_root / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    doc_path = analysis_dir / "2025-01-01-overview.md"
    doc_path.write_text(
        """---
title: Demo Overview
updated: "2025-01-01T12:00:00Z"
---
Body
""",
        encoding="utf-8",
    )

    output_dir = tmp_path / "fixtures"

    monkeypatch.setattr(module, "PROJECT_ROOT", repo_root)
    def fake_parse_args() -> argparse.Namespace:
        return argparse.Namespace(
            project="demo",
            task="task-one",
            output=output_dir,
            thread_id="thread-demo",
            process_id="proc-demo",
            environment_id="env-demo",
        )

    monkeypatch.setattr(module, "parse_args", fake_parse_args)

    try:
        module.main()
    except Exception as exc:  # pragma: no cover - diagnostic
        raise AssertionError(f"generate.main() failed: {exc}") from exc

    environments = json.loads((output_dir / "environments.json").read_text(encoding="utf-8"))
    assert environments and environments[0]["slug"] == "aware-dev"

    events_dir = output_dir / "events"
    event_files = list(events_dir.glob("*.json"))
    assert event_files, "Expected generated event files"
    payload = json.loads(event_files[0].read_text(encoding="utf-8"))
    assert payload and payload[0]["doc_path"].endswith("2025-01-01-overview.md")
