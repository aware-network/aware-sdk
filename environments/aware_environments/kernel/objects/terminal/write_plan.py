"""OperationPlan builders for terminal descriptor persistence."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from aware_environment.fs import (
    EnsureInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)
from .._shared.fs_utils import _safe_load_json
from ..thread.schemas import ThreadEntry, ThreadParticipantsManifest


def _iso_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class TerminalPlanResult:
    """Aggregate terminal filesystem operations with the resulting payload."""

    plans: Tuple[OperationPlan, ...]
    payload: Dict[str, object]


def plan_descriptor_write(
    *,
    function_name: str,
    descriptor_path: Path,
    descriptor: Mapping[str, object],
    thread_id: str,
    terminal_id: str,
    event: str,
) -> OperationPlan:
    """Return an operation plan that writes the terminal descriptor."""

    selectors = {
        "thread": thread_id,
        "terminal": terminal_id,
    }
    context = OperationContext(object_type="terminal", function=function_name, selectors=selectors)

    policy = OperationWritePolicy.WRITE_ONCE if event == "created" else OperationWritePolicy.MODIFIABLE
    timestamp = _iso_now()
    content = json.dumps(descriptor, indent=2) + "\n"

    write_instruction = WriteInstruction(
        path=descriptor_path,
        content=content,
        policy=policy,
        event=event,
        doc_type="terminal-descriptor",
        timestamp=timestamp,
        metadata={"thread": thread_id, "terminal": terminal_id},
    )

    ensure_instruction = EnsureInstruction(path=descriptor_path.parent)

    return OperationPlan(
        context=context,
        ensure_dirs=(ensure_instruction,),
        writes=(write_instruction,),
    )


def plan_participants_manifest(
    entry: ThreadEntry,
    *,
    function_name: str,
    manifest: ThreadParticipantsManifest,
) -> Tuple[OperationPlan, Path]:
    """Create a plan to write the participants manifest for a thread."""

    manifest_path = entry.directory / "participants.json"
    manifest.updated_at = _iso_now()
    manifest_payload = manifest.model_dump_json_ready()

    selectors = {
        "thread": entry.thread_id or f"{entry.process_slug}/{entry.thread_slug}",
    }
    context = OperationContext(object_type="terminal", function=function_name, selectors=selectors)

    plan = OperationPlan(
        context=context,
        ensure_dirs=(EnsureInstruction(path=manifest_path.parent),),
        writes=(
            WriteInstruction(
                path=manifest_path,
                content=json.dumps(manifest_payload, indent=2) + "\n",
                policy=OperationWritePolicy.MODIFIABLE,
                event="modified",
                doc_type="terminal-participants",
                timestamp=manifest.updated_at,
                metadata={"thread": selectors["thread"]},
            ),
        ),
    )

    return plan, manifest_path


def plan_pane_manifest(
    entry: ThreadEntry,
    *,
    function_name: str,
    pane_kind: str,
    branch_data: Optional[dict],
    pane_payload: Optional[dict],
    manifest_version: int,
) -> Tuple[OperationPlan, Path, Path, dict, dict]:
    """Create a plan to write branch and pane manifests for a terminal pane."""

    sanitised = pane_kind.lower()
    branch_path = entry.directory / "branches" / f"{sanitised}.json"
    manifest_path = entry.directory / "pane_manifests" / f"{sanitised}.json"

    existing_branch = _safe_load_json(branch_path) or {}
    existing_manifest = _safe_load_json(manifest_path) or {}

    branch = dict(existing_branch)
    if branch_data:
        branch.update(branch_data)

    branch_id = branch.get("branch_id") or branch.get("id") or uuid.uuid4().hex
    now_iso = _iso_now().isoformat().replace("+00:00", "Z")

    branch["branch_id"] = branch_id
    branch["id"] = branch_id
    branch.setdefault("pane_kind", pane_kind)
    branch.setdefault("created_at", existing_branch.get("created_at") or now_iso)
    branch["updated_at"] = now_iso
    branch.setdefault("is_main", bool(existing_branch.get("is_main", False)))

    pane_manifest = dict(existing_manifest)
    pane_manifest.setdefault("pane_kind", pane_kind)
    pane_manifest["branch_id"] = branch_id
    pane_manifest.setdefault("manifest_version", manifest_version)
    if pane_payload is not None:
        pane_manifest["payload"] = pane_payload
    else:
        pane_manifest.setdefault("payload", existing_manifest.get("payload") or {})

    selectors = {
        "thread": entry.thread_id or f"{entry.process_slug}/{entry.thread_slug}",
        "pane": pane_kind,
    }
    context = OperationContext(object_type="terminal", function=function_name, selectors=selectors)

    writes = (
        WriteInstruction(
            path=branch_path,
            content=json.dumps(branch, indent=2) + "\n",
            policy=OperationWritePolicy.MODIFIABLE,
            event="modified",
            doc_type="terminal-branch",
            timestamp=datetime.now(timezone.utc),
            metadata={"pane": pane_kind},
        ),
        WriteInstruction(
            path=manifest_path,
            content=json.dumps(pane_manifest, indent=2) + "\n",
            policy=OperationWritePolicy.MODIFIABLE,
            event="modified",
            doc_type="terminal-pane-manifest",
            timestamp=datetime.now(timezone.utc),
            metadata={"pane": pane_kind},
        ),
    )

    plan = OperationPlan(
        context=context,
        ensure_dirs=(
            EnsureInstruction(path=branch_path.parent),
            EnsureInstruction(path=manifest_path.parent),
        ),
        writes=writes,
    )

    return plan, branch_path, manifest_path, branch, pane_manifest


__all__ = ["TerminalPlanResult", "plan_descriptor_write", "plan_participants_manifest", "plan_pane_manifest"]
