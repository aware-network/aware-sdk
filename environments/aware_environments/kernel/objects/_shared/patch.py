"""Helpers for building patch-based operation plans."""

from __future__ import annotations

from datetime import datetime
from difflib import unified_diff
from pathlib import Path
from typing import Mapping, Tuple

from aware_environment.fs import OperationWritePolicy, PatchInstruction


def build_patch_instruction_from_text(
    *,
    path: Path,
    original_text: str,
    updated_text: str,
    doc_type: str,
    timestamp: datetime,
    policy: OperationWritePolicy,
    metadata: Mapping[str, object],
    summary: str | None = None,
    event: str | None = None,
) -> Tuple[PatchInstruction | None, str]:
    """Return a PatchInstruction describing the diff between two text blobs.

    If no textual change is detected the function returns ``(None, "")`` so
    callers can skip emitting patch instructions.
    """

    if original_text == updated_text:
        return None, ""

    diff_text = "".join(
        unified_diff(
            original_text.splitlines(keepends=True),
            updated_text.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )

    if not diff_text.strip():
        return None, ""

    hook_metadata: dict[str, object] = {}
    if summary:
        hook_metadata.setdefault("summary", summary)

    instruction = PatchInstruction(
        path=Path(path),
        diff=diff_text,
        policy=policy,
        doc_type=doc_type,
        timestamp=timestamp,
        metadata=dict(metadata),
        hook_metadata=hook_metadata,
        summary=summary,
        event=event,
    )
    return instruction, diff_text


__all__ = ["build_patch_instruction_from_text"]

