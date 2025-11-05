"""Plan builders for task lifecycle operations."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

from .._shared.frontmatter import load_frontmatter
from .._shared.patch import build_patch_instruction_from_text
from aware_environment.fs import (
    EnsureInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)


@dataclass(frozen=True)
class TaskPlanResult:
    """Wrapper containing an operation plan and serialized payload."""

    plan: OperationPlan
    payload: Dict[str, Any]


def _iso_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slugify(value: str) -> str:
    lowered = value.strip().lower().replace(" ", "-").replace("/", "-")
    cleaned = re.sub(r"[^a-z0-9\-]+", "-", lowered)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "untitled"


def _compose_document(metadata: Dict[str, Any], content: str) -> str:
    header = yaml.safe_dump(metadata, sort_keys=False).strip()
    body = content.rstrip()
    if body:
        return f"---\n{header}\n---\n\n{body}\n"
    return f"---\n{header}\n---\n"


def _merge_body(existing: str, addition: str) -> str:
    existing = existing.rstrip()
    addition = addition.rstrip()
    if not addition:
        return existing
    if not existing:
        return addition + "\n"
    return f"{existing}\n\n{addition}\n"


def _find_task_directory(projects_root: Path, project_slug: str, task_slug: str) -> Path:
    project_path = projects_root / project_slug
    tasks_root = project_path / "tasks"
    search_paths = [
        tasks_root / task_slug,
        tasks_root / "_pending" / task_slug,
        tasks_root / "_completed" / task_slug,
    ]
    for candidate in search_paths:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Task '{task_slug}' not found under project '{project_slug}'.")


def _build_context(
    projects_root: Path,
    project_slug: str,
    task_slug: str,
    function_name: str,
) -> Tuple[OperationContext, Path]:
    task_dir = _find_task_directory(projects_root, project_slug, task_slug)
    project_path = projects_root / project_slug
    tasks_root = project_path / "tasks"
    relative = task_dir.relative_to(tasks_root)
    parts = relative.parts
    bucket = parts[0] if parts and parts[0] in {"_pending", "_completed"} else ""
    selectors = {
        "project": project_slug,
        "task": task_slug,
        "project_slug": project_slug,
        "task_slug": task_slug,
        "task_bucket": bucket,
    }
    context = OperationContext(object_type="task", function=function_name, selectors=selectors)
    return context, task_dir


def plan_task_document(
    projects_root: Path,
    *,
    function_name: str,
    project_slug: str,
    task_slug: str,
    subdir: str,
    doc_type: str,
    title: str,
    slug: Optional[str],
    summary: str,
    content: str,
    author: Dict[str, str],
    version_bump: Optional[str] = None,
) -> TaskPlanResult:
    context, task_dir = _build_context(projects_root, project_slug, task_slug, function_name)
    now = _iso_now()
    iso_stamp = _isoformat(now)

    resolved_slug = (slug or _slugify(title)).strip() or "untitled"
    filename_stamp = iso_stamp.replace(":", "-")
    filename = f"{filename_stamp}-{resolved_slug}.md"
    target = task_dir / subdir / filename

    metadata: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "title": title.strip(),
        "slug": resolved_slug,
        "created": iso_stamp,
        "updated": iso_stamp,
        "author": author,
        "summary": summary,
    }

    hook_metadata: Dict[str, Any] = {}
    if doc_type == "design":
        metadata["version"] = "0.0.0"
        if version_bump:
            hook_metadata["version_bump"] = version_bump.lower()

    document_text = _compose_document(metadata, content)

    write_instruction = WriteInstruction(
        path=target,
        content=document_text,
        policy=OperationWritePolicy.WRITE_ONCE,
        event="created",
        doc_type=doc_type,
        timestamp=now,
        metadata=metadata,
        hook_metadata=hook_metadata,
    )

    payload: Dict[str, Any] = {
        "project": project_slug,
        "task": task_slug,
        "doc_type": doc_type,
        "path": target,
        "slug": metadata["slug"],
        "title": metadata["title"],
        "summary": metadata["summary"],
        "created": metadata["created"],
        "updated": metadata["updated"],
    }
    if "version" in metadata:
        payload["version"] = metadata["version"]
    if hook_metadata:
        payload["hook_metadata"] = hook_metadata

    plan = OperationPlan(
        context=context,
        ensure_dirs=(EnsureInstruction(path=target.parent),),
        writes=(write_instruction,),
    )
    return TaskPlanResult(plan=plan, payload=payload)


def plan_task_backlog(
    projects_root: Path,
    *,
    function_name: str,
    project_slug: str,
    task_slug: str,
    title: str,
    slug: Optional[str],
    summary: str,
    content: str,
    author: Dict[str, str],
) -> TaskPlanResult:
    context, task_dir = _build_context(projects_root, project_slug, task_slug, function_name)
    base_dir = task_dir / "backlog"
    now = _iso_now()
    timestamp = _isoformat(now)
    date_slug = now.strftime("%Y-%m-%d")
    resolved_slug = (slug or f"{task_slug}-backlog-{date_slug}").strip() or f"{task_slug}-backlog-{date_slug}"
    target = base_dir / f"{date_slug}.md"

    entry_body = content or summary or "- TODO: fill in backlog entry"
    addition = f"[{timestamp}]\n{entry_body.rstrip()}".rstrip() + "\n"

    ensure_dirs = [EnsureInstruction(path=base_dir)]
    writes: List[WriteInstruction] = []
    patches = []

    if not target.exists():
        metadata = {
            "id": str(uuid.uuid4()),
            "title": title.strip(),
            "slug": resolved_slug,
            "created": timestamp,
            "updated": timestamp,
            "author": author,
            "summary": summary or "",
        }
        document_text = _compose_document(metadata, addition)
        event = "created"
        writes.append(
            WriteInstruction(
                path=target,
                content=document_text,
                policy=OperationWritePolicy.APPEND_ENTRY,
                event=event,
                doc_type="backlog",
                timestamp=now,
                metadata=metadata,
            )
        )
    else:
        original_text = target.read_text(encoding="utf-8")
        fm = load_frontmatter(target)
        original_metadata = dict(fm.metadata)
        updated_metadata = dict(original_metadata)
        updated_metadata.setdefault("id", str(uuid.uuid4()))
        updated_metadata.setdefault("title", title.strip())
        updated_metadata["slug"] = resolved_slug
        updated_metadata["author"] = author
        if summary:
            updated_metadata["summary"] = summary
        else:
            updated_metadata.setdefault("summary", "")

        combined_body = _merge_body(fm.body, addition)
        provisional_doc = _compose_document(updated_metadata, combined_body)

        if provisional_doc == original_text:
            metadata = original_metadata
            event = "unchanged"
        else:
            updated_metadata["updated"] = timestamp
            document_text = _compose_document(updated_metadata, combined_body)
            summary_text = summary or entry_body.splitlines()[0]
            patch_instruction, _ = build_patch_instruction_from_text(
                path=target,
                original_text=original_text,
                updated_text=document_text,
                doc_type="backlog",
                timestamp=now,
                policy=OperationWritePolicy.APPEND_ENTRY,
                metadata=updated_metadata,
                summary=summary_text,
                event="appended",
            )
            if patch_instruction is not None:
                patches.append(patch_instruction)
                metadata = updated_metadata
                event = "appended"
            else:
                metadata = original_metadata
                event = "unchanged"

    payload: Dict[str, Any] = {
        "project": project_slug,
        "task": task_slug,
        "doc_type": "backlog",
        "path": target,
        "slug": metadata.get("slug"),
        "title": metadata.get("title"),
        "summary": metadata.get("summary"),
        "event": event,
        "timestamp": timestamp,
    }

    plan = OperationPlan(
        context=context,
        ensure_dirs=tuple(ensure_dirs),
        writes=tuple(writes),
        patches=tuple(patches),
    )
    return TaskPlanResult(plan=plan, payload=payload)


_TIMESTAMP_HEADING_PATTERN = re.compile(r"^\[\d{4}-\d{2}-\d{2}T")
_DEFAULT_OVERVIEW_SECTIONS: Tuple[str, ...] = ("Status", "Objectives", "Next Steps")


def _canonical_heading(name: str) -> str:
    base = name.strip()
    if ":" in base:
        base = base.split(":", 1)[0]
    mapping = {
        "status": "Status",
        "objectives": "Objectives",
        "next steps": "Next Steps",
    }
    return mapping.get(base.lower(), base.strip())


def _parse_heading_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    stripped = line.strip()
    if not stripped.startswith("##"):
        return None, None
    candidate = stripped[2:].strip()
    inline = None
    if ":" in candidate:
        head, rest = candidate.split(":", 1)
        candidate = head.strip()
        inline = rest.strip()
    return _canonical_heading(candidate), inline


def _collect_body_sections(body: str) -> Tuple[List[str], Dict[str, str]]:
    lines = body.splitlines()
    order: List[str] = []
    sections: Dict[str, str] = {}
    current_heading: Optional[str] = None
    buffer: List[str] = []
    preface: List[str] = []

    def flush_preface() -> None:
        nonlocal preface
        if preface:
            content = "\n".join(preface).strip("\n")
            if content:
                heading = "Status"
                if heading not in sections:
                    order.append(heading)
                sections[heading] = content
            preface = []

    def flush_section(heading: Optional[str], collected: List[str]) -> None:
        if heading is None:
            return
        content = "\n".join(collected).strip("\n")
        if heading not in sections:
            order.append(heading)
        sections[heading] = content

    for line in lines:
        trimmed = line.strip()
        if _TIMESTAMP_HEADING_PATTERN.match(trimmed):
            if current_heading is not None:
                flush_section(current_heading, buffer)
                current_heading = None
                buffer = []
            continue
        heading, inline = _parse_heading_line(line)
        if heading is not None:
            if current_heading is None:
                flush_preface()
            else:
                flush_section(current_heading, buffer)
            current_heading = heading
            buffer = []
            if inline:
                buffer.append(inline)
            continue

        if current_heading is None:
            preface.append(line)
        else:
            buffer.append(line)

    if current_heading is None:
        flush_preface()
    else:
        flush_section(current_heading, buffer)

    if not order and not sections:
        order = list(_DEFAULT_OVERVIEW_SECTIONS)
        sections = {heading: "" for heading in order}

    return order, sections


def _parse_overview_updates(content: str) -> List[Tuple[str, str]]:
    text = content.strip("\n")
    if not text.strip():
        return []
    lines = text.splitlines()
    order: List[str] = []
    sections: Dict[str, str] = {}
    current_heading: Optional[str] = None
    buffer: List[str] = []

    def flush(heading: Optional[str], collected: List[str]) -> None:
        if heading is None:
            return
        content = "\n".join(collected).strip("\n")
        if heading not in sections:
            order.append(heading)
        sections[heading] = content

    for line in lines:
        heading, inline = _parse_heading_line(line)
        if heading is not None:
            flush(current_heading, buffer)
            current_heading = heading
            buffer = []
            if inline:
                buffer.append(inline)
            continue
        if current_heading is None:
            current_heading = "Status"
            buffer = []
        buffer.append(line)

    flush(current_heading, buffer)
    return [(heading, sections[heading]) for heading in order]


def _canonical_section_order(existing: Sequence[str], updates: Sequence[str]) -> List[str]:
    ordered: List[str] = list(_DEFAULT_OVERVIEW_SECTIONS)
    for heading in existing:
        if heading not in ordered:
            ordered.append(heading)
    for heading in updates:
        if heading not in ordered:
            ordered.append(heading)
    return ordered


def _render_overview_body(order: Sequence[str], sections: Dict[str, str]) -> str:
    blocks: List[str] = []
    for heading in order:
        body = sections.get(heading, "")
        lines = [f"## {heading}"]
        if body:
            lines.append(body.rstrip())
        blocks.append("\n".join(lines).rstrip())
    rendered = "\n\n".join(blocks).rstrip()
    if rendered:
        return rendered + "\n"
    return rendered


def plan_task_overview(
    projects_root: Path,
    *,
    function_name: str,
    project_slug: str,
    task_slug: str,
    title: str,
    slug: Optional[str],
    summary: str,
    content: str,
    author: Dict[str, str],
) -> TaskPlanResult:
    context, task_dir = _build_context(projects_root, project_slug, task_slug, function_name)
    path = task_dir / "OVERVIEW.md"
    now = _iso_now()
    timestamp = _isoformat(now)
    resolved_slug = (slug or _slugify(title)).strip() or _slugify(title)

    ensure_dirs = [EnsureInstruction(path=path.parent)]
    writes: List[WriteInstruction] = []
    patches = []

    if not path.exists():
        metadata = {
            "id": str(uuid.uuid4()),
            "title": title.strip(),
            "slug": resolved_slug,
            "created": timestamp,
            "updated": timestamp,
            "author": author,
            "summary": summary,
        }
        updates = _parse_overview_updates(content)
        update_headings = [heading for heading, _ in updates]
        canonical_order = _canonical_section_order([], update_headings)
        sections = {heading: "" for heading in canonical_order}

        default_status = content.strip("\n")
        if not updates and default_status:
            sections["Status"] = default_status.strip("\n")
        if not default_status and summary and "Status" in sections:
            sections["Status"] = summary.strip()
        for heading, body_chunk in updates:
            sections[heading] = body_chunk.rstrip()
        body_text = _render_overview_body(canonical_order, sections)
        document_text = _compose_document(metadata, body_text)
        event = "created"
        writes.append(
            WriteInstruction(
                path=path,
                content=document_text,
                policy=OperationWritePolicy.MODIFIABLE,
                event=event,
                doc_type="overview",
                timestamp=now,
                metadata=metadata,
            )
        )
    else:
        original_text = path.read_text(encoding="utf-8")
        fm = load_frontmatter(path)
        original_metadata = dict(fm.metadata)
        updated_metadata = dict(original_metadata)
        updated_metadata.setdefault("id", str(uuid.uuid4()))
        updated_metadata.setdefault("title", title.strip())
        updated_metadata["slug"] = resolved_slug
        updated_metadata["author"] = author
        if summary:
            updated_metadata["summary"] = summary
        else:
            updated_metadata.setdefault("summary", "")

        existing_order, existing_sections = _collect_body_sections(fm.body)
        updates = _parse_overview_updates(content)
        update_headings = [heading for heading, _ in updates]
        canonical_order = _canonical_section_order(existing_order, update_headings)
        sections = dict(existing_sections)
        for heading in canonical_order:
            sections.setdefault(heading, "")
        for heading, body_chunk in updates:
            sections[heading] = body_chunk.rstrip()
        body_text = _render_overview_body(canonical_order, sections)

        provisional_doc = _compose_document(updated_metadata, body_text)
        if provisional_doc == original_text:
            metadata = original_metadata
            event = "unchanged"
        else:
            updated_metadata["updated"] = timestamp
            document_text = _compose_document(updated_metadata, body_text)
            summary_text = summary or f"Updated overview for {task_slug}"
            patch_instruction, _ = build_patch_instruction_from_text(
                path=path,
                original_text=original_text,
                updated_text=document_text,
                doc_type="overview",
                timestamp=now,
                policy=OperationWritePolicy.MODIFIABLE,
                metadata=updated_metadata,
                summary=summary_text,
                event="modified",
            )
            if patch_instruction is not None:
                patches.append(patch_instruction)
                metadata = updated_metadata
                event = "modified"
            else:
                metadata = original_metadata
                event = "unchanged"

    payload: Dict[str, Any] = {
        "project": project_slug,
        "task": task_slug,
        "doc_type": "overview",
        "path": path,
        "slug": metadata.get("slug"),
        "title": metadata.get("title"),
        "summary": metadata.get("summary"),
        "updated": metadata.get("updated"),
        "event": event,
    }

    plan = OperationPlan(
        context=context,
        ensure_dirs=tuple(ensure_dirs),
        writes=tuple(writes),
        patches=tuple(patches),
    )
    return TaskPlanResult(plan=plan, payload=payload)


__all__ = [
    "plan_task_document",
    "plan_task_backlog",
    "plan_task_overview",
    "TaskPlanResult",
]
