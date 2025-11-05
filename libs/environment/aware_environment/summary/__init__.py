"""Shared summary formatter for environment-aware tooling."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple
import re
import sys

BADGES: dict[str, str] = {
    "analysis": "[A]",
    "design": "[D]",
    "change": "[C]",
    "backlog": "[B]",
    "overview": "[O]",
    "index": "[I]",
    "thread-branch": "[TB]",
}

BADGE_TO_TYPE: dict[str, str] = {badge: doc_type for doc_type, badge in BADGES.items()}

ANSI_COLORS: dict[str, str] = {
    "analysis": "\033[36m",
    "design": "\033[35m",
    "change": "\033[31m",
    "backlog": "\033[33m",
    "overview": "\033[32m",
    "index": "\033[34m",
    "thread-branch": "\033[36m",
}

ANSI_RESET = "\033[0m"

DOC_TYPE_ORDER: list[str] = [
    "overview",
    "analysis",
    "design",
    "change",
    "backlog",
    "index",
    "thread-branch",
]


@dataclass(slots=True)
class SummaryDocument:
    """Document metadata required to render update summaries."""

    doc_type: str
    path: str
    metadata: Mapping[str, Any] | None = None


@dataclass(slots=True)
class SummaryEvent:
    """Lightweight update event shared between CLI and environment."""

    project_slug: str
    task_slug: str
    document: SummaryDocument
    event_type: str
    detected_at: datetime


@dataclass(slots=True)
class DocSummary:
    """Rendered summary row for a single document event."""

    doc_type: str
    label: str
    path: str
    detected_at: datetime
    display: str
    event_type: str
    title: str | None = None


@dataclass(slots=True)
class SummaryBlock:
    """Bundle of summary lines for a given project/task/audience."""

    project: str
    task: str
    audience: str
    lines: list[str]
    docs: list[DocSummary] | None = None


@dataclass(slots=True)
class ContentChainEntry:
    """Content chain payload used by status snapshot writers."""

    audience: str
    parts: list[str] = field(default_factory=list)
    truncated: bool = False
    hidden_count: int = 0
    budget: int | None = None


def build_summary_blocks(
    events: Iterable[SummaryEvent],
    *,
    audiences: Sequence[str],
    limit: int,
) -> list[SummaryBlock]:
    """Group summary events by project/task and render audience-specific blocks."""

    limit = max(limit, 0)
    grouped: dict[tuple[str, str], MutableMapping[str, list[SummaryEvent]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for event in events:
        key = (event.project_slug, event.task_slug)
        grouped[key][event.document.doc_type].append(event)

    blocks: list[SummaryBlock] = []

    for (project_slug, task_slug), doc_map in sorted(grouped.items()):
        for doc_events in doc_map.values():
            doc_events.sort(key=lambda e: e.detected_at, reverse=True)

        doc_summaries = _build_doc_summaries(doc_map, limit)

        for audience in audiences:
            if audience == "human":
                lines = [summary.display for summary in doc_summaries]
                docs = doc_summaries
            else:
                lines = _render_agent(doc_map, limit)
                docs = None
            if lines:
                blocks.append(
                    SummaryBlock(
                        project=project_slug,
                        task=task_slug,
                        audience=audience,
                        lines=lines,
                        docs=docs,
                    )
                )

    return blocks


def render_summary_text(
    blocks: Iterable[SummaryBlock],
    *,
    color: str = "auto",
    max_chars: int | None = None,
    no_truncate: bool = False,
    stdout_isatty: bool | None = None,
) -> str:
    """Render summary blocks into coloured/plain-text output."""

    if stdout_isatty is None:
        stdout_isatty = sys.stdout.isatty()

    enable_color = color == "always" or (color == "auto" and stdout_isatty)

    parts: list[str] = []
    for block in blocks:
        if block.audience == "human":
            parts.append(f"Project: {block.project}")
            parts.append(f"  Task: {block.task}")
            indent = "    "
        else:
            parts.append(f"{block.project} / {block.task}")
            parts.append(f"- audience: {block.audience}")
            indent = "  "
        for line in block.lines:
            parts.append((indent + colorize_badges(line, enable_color)).rstrip())
        parts.append("")

    summary = "\n".join(parts).rstrip()

    if max_chars and max_chars > 0 and len(summary) > max_chars and not no_truncate:
        truncated = summary[: max_chars - 1].rstrip()
        summary = f"{truncated}\n… (truncated)"

    return summary


def format_doc_summary_line(doc_type: str, detected_at: datetime, label: str) -> str:
    """Return the badge/timestamp label for human summaries."""

    badge = _badge(doc_type)
    timestamp = _format_timestamp(detected_at)
    return f"{badge} {timestamp} → {label}"


def colorize_badges(text: str, enable: bool) -> str:
    """Colourise summary badges when supported by the caller."""

    if not enable:
        return text

    result = text
    for badge, doc_type in BADGE_TO_TYPE.items():
        color = ANSI_COLORS.get(doc_type)
        if color:
            result = result.replace(badge, f"{color}{badge}{ANSI_RESET}")
    return result


def format_snapshot_label(path: str, stored_label: str | None, metadata: Mapping[str, Any] | None = None) -> str:
    """Create a stable label for status snapshot entries."""

    if stored_label:
        return stored_label
    label, _ = derive_doc_label(path, metadata)
    return label


TIMESTAMP_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z[-_]")
DATE_LIKE_SLUG = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}-\d{2}-\d{2}Z)?$")
TIMESTAMP_LEADING = re.compile(
    r"^\d{4}[- ]\d{2}[- ]\d{2}(?:T\d{2}[- ]\d{2}[- ]\d{2}Z?)?\s*", re.IGNORECASE
)


def derive_doc_label(path: str | Path, metadata: Mapping[str, Any] | None) -> tuple[str, str | None]:
    """Derive a human-friendly label (and title) from path/metadata."""

    meta = metadata or {}
    for key in ("title", "name", "summary"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            base = _strip_leading_timestamp(value.strip())
            title = _normalise_title(base) if base else value.strip()
            return _append_slug(path, title), title

    stem = Path(path).stem
    slug = _strip_timestamp_prefix(stem)
    prettified = _prettify_slug(slug)
    base = prettified or _strip_leading_timestamp(stem) or stem
    title = _normalise_title(base)
    return _append_slug(path, title), title


def build_content_chain_map(
    blocks: Iterable[SummaryBlock],
    budgets: Mapping[str, Optional[int]],
) -> Dict[Tuple[str, str], List[ContentChainEntry]]:
    """Convert summary blocks into content-chain payloads keyed by project/task."""

    aggregated: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = {}

    for block in blocks:
        key = (block.project, block.task)
        per_task = aggregated.setdefault(key, {})
        entry = per_task.setdefault(
            block.audience,
            {"parts": [], "consumed": 0, "hidden": 0, "budget": budgets.get(block.audience)},
        )
        if block.audience == "human":
            lines = [f"Project: {block.project}", f"  Task: {block.task}"]
            lines.extend(f"    {line}" for line in block.lines)
        else:
            lines = [f"{block.project} / {block.task}", f"- audience: {block.audience}"]
            lines.extend(f"  {line}" for line in block.lines)
        text = "\n".join(lines).rstrip()
        limit = entry["budget"]
        size = len(text)
        if limit is not None and limit > 0 and entry["consumed"] + size > limit:
            entry["hidden"] += 1
            continue
        entry["parts"].append(text)
        entry["consumed"] += size + 1

    result: Dict[Tuple[str, str], List[ContentChainEntry]] = {}
    for key, audiences in aggregated.items():
        chain_entries: List[ContentChainEntry] = []
        for audience, info in audiences.items():
            chain_entries.append(
                ContentChainEntry(
                    audience=audience,
                    parts=list(info["parts"]),
                    truncated=info["hidden"] > 0,
                    hidden_count=info["hidden"],
                    budget=info["budget"],
                )
            )
        if chain_entries:
            result[key] = chain_entries
    return result


def _build_doc_summaries(
    doc_map: Mapping[str, list[SummaryEvent]],
    limit: int,
) -> list[DocSummary]:
    summaries: list[DocSummary] = []
    collected: list[SummaryEvent] = []

    for doc_type in DOC_TYPE_ORDER:
        events = doc_map.get(doc_type, [])
        if events:
            collected.extend(events if limit == 0 else events[:limit])

    for doc_type, events in doc_map.items():
        if doc_type not in DOC_TYPE_ORDER:
            collected.extend(events if limit == 0 else events[:limit])

    collected.sort(key=lambda e: e.detected_at, reverse=True)
    if limit > 0:
        collected = collected[:limit]

    for event in collected:
        label, title = derive_doc_label(event.document.path, event.document.metadata)
        display = format_doc_summary_line(
            event.document.doc_type,
            event.detected_at,
            label,
        )
        summaries.append(
            DocSummary(
                doc_type=event.document.doc_type,
                label=label,
                path=str(event.document.path),
                detected_at=event.detected_at,
                display=display,
                event_type=str(event.event_type),
                title=title,
            )
        )

    return summaries


def _render_agent(doc_map: Mapping[str, list[SummaryEvent]], limit: int) -> list[str]:
    lines: list[str] = []

    ordered_types = sorted(
        doc_map.keys(),
        key=lambda dt: (DOC_TYPE_ORDER.index(dt) if dt in DOC_TYPE_ORDER else len(DOC_TYPE_ORDER), dt),
    )

    for doc_type in ordered_types:
        events = doc_map[doc_type]
        if not events:
            continue
        lines.append(f"{_badge(doc_type)} {doc_type}")
        limited = events if limit == 0 else events[:limit]
        for event in limited:
            timestamp = _format_timestamp(event.detected_at)
            label, _ = derive_doc_label(event.document.path, event.document.metadata)
            path = str(event.document.path)
            lines.append(f" - {timestamp} → {label} ({path})")

    return lines


def _format_timestamp(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _badge(doc_type: str) -> str:
    return BADGES.get(doc_type, "[?]")


def _strip_timestamp_prefix(stem: str) -> str:
    if TIMESTAMP_PREFIX.match(stem):
        remainder = stem[20:]
        if remainder.startswith(("-", "_")):
            remainder = remainder[1:]
        return remainder
    return stem


def _prettify_slug(slug: str) -> str:
    if not slug:
        return ""
    if DATE_LIKE_SLUG.match(slug):
        return slug
    words = slug.replace("-", " ").replace("_", " ").strip()
    if not words:
        return slug
    return words.title()


def _strip_leading_timestamp(text: str) -> str:
    if not text:
        return ""
    return TIMESTAMP_LEADING.sub("", text).strip()


def _normalise_title(text: str) -> str:
    if not text:
        return ""
    return text.title()


def _append_slug(path: str | Path, title: str) -> str:
    stem = Path(path).stem
    slug = _strip_timestamp_prefix(stem)
    if slug and slug not in title:
        return f"{title} ({slug})"
    return title
