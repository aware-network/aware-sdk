"""Tests for aware_environment.summary module."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aware_environment.summary import (
    ContentChainEntry,
    SummaryDocument,
    SummaryEvent,
    build_content_chain_map,
    build_summary_blocks,
    colorize_badges,
    derive_doc_label,
    format_doc_summary_line,
    render_summary_text,
)


def _make_event(
    *,
    project: str = "aware-project",
    task: str = "sample-task",
    doc_type: str = "analysis",
    title: str | None = "Initial analysis",
    timestamp: datetime | None = None,
) -> SummaryEvent:
    detected_at = timestamp or datetime(2025, 10, 27, 0, 0, 0, tzinfo=timezone.utc)
    metadata = {"title": title} if title else {}
    document = SummaryDocument(
        doc_type=doc_type,
        path="docs/projects/aware-project/tasks/sample-task/analysis/2025-10-27T00-00-00Z-analysis.md",
        metadata=metadata,
    )
    return SummaryEvent(
        project_slug=project,
        task_slug=task,
        document=document,
        event_type="created",
        detected_at=detected_at,
    )


def test_build_summary_blocks_human_audience() -> None:
    events = [
        _make_event(doc_type="analysis"),
        _make_event(doc_type="design", title="Design notes", timestamp=datetime(2025, 10, 27, 1, 0, tzinfo=timezone.utc)),
    ]

    blocks = build_summary_blocks(events, audiences=["human"], limit=5)

    assert len(blocks) == 1
    block = blocks[0]
    assert block.project == "aware-project"
    assert block.task == "sample-task"
    assert block.audience == "human"
    assert any("[A]" in line for line in block.lines), "analysis badge should be present"
    assert any("[D]" in line for line in block.lines), "design badge should be present"
    assert block.docs is not None
    assert len(block.docs) == 2
    titles = {doc.title for doc in block.docs}
    assert "Initial Analysis" in titles
    assert "Design Notes" in titles


def test_render_summary_text_agent_audience() -> None:
    event = _make_event()
    blocks = build_summary_blocks([event], audiences=["agent"], limit=5)

    text = render_summary_text(blocks, color="never", stdout_isatty=False)

    assert "aware-project / sample-task" in text
    assert "- audience: agent" in text
    assert "[A] analysis" in text


def test_content_chain_budget_truncation() -> None:
    events = [_make_event()]
    blocks = build_summary_blocks(events, audiences=["human"], limit=5)

    chain_map = build_content_chain_map(blocks, {"human": 10})

    key = ("aware-project", "sample-task")
    assert key in chain_map
    entries = chain_map[key]
    assert len(entries) == 1
    entry = entries[0]
    assert isinstance(entry, ContentChainEntry)
    assert entry.audience == "human"
    assert entry.truncated is True
    assert entry.hidden_count == 1


def test_format_doc_summary_line_uses_badge_and_timestamp() -> None:
    detected_at = datetime(2025, 10, 27, 2, 15, 30, tzinfo=timezone.utc)

    line = format_doc_summary_line("analysis", detected_at, "Initial Analysis")

    assert line.startswith("[A] 2025-10-27T02:15:30Z"), line
    assert line.endswith("Initial Analysis"), line


def test_colorize_badges_injects_ansi() -> None:
    text = "[A] Analysis line"

    colored = colorize_badges(text, enable=True)

    assert "\033[" in colored
    assert colored.startswith("\033[36m[A]\033[0m"), colored
    assert colored.endswith("Analysis line"), colored


@pytest.mark.parametrize(
    ("path", "metadata", "expected"),
    [
            (
                "docs/projects/proj/tasks/task/analysis/2025-10-27T00-00-00Z-summary.md",
                {"title": "Auth investigation"},
                "Auth Investigation (summary)",
            ),
            (
                "docs/projects/proj/tasks/task/design/alpha.md",
                {},
                "Alpha (alpha)",
            ),
    ],
)
def test_derive_doc_label(path: str, metadata: dict[str, str], expected: str) -> None:
    label, _ = derive_doc_label(path, metadata)

    assert label == expected
