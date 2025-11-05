"""OperationPlan builders for thread branch and participant persistence."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from aware_environment.fs import (
    EnsureInstruction,
    MoveInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)

from .._shared.fs_utils import _safe_load_json
from .schemas import ThreadEntry, ThreadParticipantsManifest


def _iso_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sanitize_pane_kind(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "-", value.lower())


def _sanitize_branch_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", value)


@dataclass(frozen=True)
class ThreadPlanResult:
    plans: Tuple[OperationPlan, ...]
    payload: Dict[str, object]


def _resolve_branch_paths(entry: ThreadEntry, pane_kind: str, branch_id: str | None) -> tuple[Path, Path]:
    sanitised_pane = _sanitize_pane_kind(pane_kind)
    if branch_id:
        sanitised_branch = _sanitize_branch_id(branch_id)
        branch_path = entry.directory / "branches" / sanitised_pane / f"{sanitised_branch}.json"
        manifest_path = entry.directory / "pane_manifests" / sanitised_pane / f"{sanitised_branch}.json"
    else:
        branch_path = entry.directory / "branches" / f"{sanitised_pane}.json"
        manifest_path = entry.directory / "pane_manifests" / f"{sanitised_pane}.json"
    return branch_path, manifest_path


def _prepare_branch_payload(
    entry: ThreadEntry,
    *,
    pane_kind: str,
    branch: Dict[str, object] | None,
    pane_manifest: Dict[str, object] | None,
    manifest_version: int,
) -> tuple[Dict[str, object], Dict[str, object], Path, Path, str, str]:
    branch_data = dict(branch or {})
    branch_id = str(branch_data.get("branch_id") or branch_data.get("id") or uuid.uuid4().hex)
    branch_path, manifest_path = _resolve_branch_paths(entry, pane_kind, branch_id)

    branch_event = "created" if not branch_path.exists() else "updated"
    manifest_event = "created" if not manifest_path.exists() else "updated"

    now_iso = _isoformat(_iso_now())
    branch_data.setdefault("pane_kind", pane_kind)
    branch_data.setdefault("created_at", branch_data.get("created_at") or now_iso)
    branch_data.setdefault("is_main", bool(branch_data.get("is_main", False)))
    branch_data["updated_at"] = now_iso
    branch_data["branch_id"] = branch_id
    branch_data["id"] = branch_id

    manifest_data = dict(pane_manifest or {})
    manifest_data.setdefault("pane_kind", pane_kind)
    manifest_data["branch_id"] = branch_id
    manifest_data["manifest_version"] = manifest_version
    manifest_data.setdefault("payload", manifest_data.get("payload") or {})

    return branch_data, manifest_data, branch_path, manifest_path, branch_event, manifest_event


def plan_branch_write(
    entry: ThreadEntry,
    *,
    function_name: str,
    pane_kind: str,
    branch: Dict[str, object] | None,
    pane_manifest: Dict[str, object] | None,
    manifest_version: int,
    task_binding: Dict[str, object] | None = None,
) -> ThreadPlanResult:
    branch_data, manifest_data, branch_path, manifest_path, branch_event, manifest_event = _prepare_branch_payload(
        entry,
        pane_kind=pane_kind,
        branch=branch,
        pane_manifest=pane_manifest,
        manifest_version=manifest_version,
    )

    selectors = {
        "process": entry.process_slug,
        "thread": entry.thread_slug,
        "pane": pane_kind,
    }
    context = OperationContext(object_type="thread", function=function_name, selectors=selectors)

    ensure_dirs = {
        branch_path.parent,
        manifest_path.parent,
    }

    now = _iso_now()
    writes = [
        WriteInstruction(
            path=branch_path,
            content=json.dumps(branch_data, indent=2) + "\n",
            policy=OperationWritePolicy.WRITE_ONCE if branch_event == "created" else OperationWritePolicy.MODIFIABLE,
            event=branch_event,
            doc_type="thread-branch",
            timestamp=now,
            metadata={
                "process": entry.process_slug,
                "thread": entry.thread_slug,
                "pane": pane_kind,
            },
        ),
        WriteInstruction(
            path=manifest_path,
            content=json.dumps(manifest_data, indent=2) + "\n",
            policy=OperationWritePolicy.WRITE_ONCE if manifest_event == "created" else OperationWritePolicy.MODIFIABLE,
            event=manifest_event,
            doc_type="thread-pane-manifest",
            timestamp=now,
            metadata={
                "process": entry.process_slug,
                "thread": entry.thread_slug,
                "pane": pane_kind,
            },
        ),
    ]

    if task_binding:
        metadata_path = entry.directory / "thread.json"
        thread_doc = _safe_load_json(metadata_path) or {}
        tasks = thread_doc.get("thread_task_list")
        if not isinstance(tasks, list):
            tasks = []
        binding_task_id = task_binding.get("task_id")
        if binding_task_id:
            tasks = [item for item in tasks if isinstance(item, dict) and item.get("task_id") != binding_task_id]
        tasks.append(task_binding)
        thread_doc["thread_task_list"] = tasks
        ensure_dirs.add(metadata_path.parent)
        writes.append(
            WriteInstruction(
                path=metadata_path,
                content=json.dumps(thread_doc, indent=2) + "\n",
                policy=OperationWritePolicy.MODIFIABLE,
                event="updated" if metadata_path.exists() else "created",
                doc_type="thread-metadata",
                timestamp=_iso_now(),
                metadata={
                    "process": entry.process_slug,
                    "thread": entry.thread_slug,
                },
            )
        )

    plan = OperationPlan(
        context=context,
        ensure_dirs=tuple(EnsureInstruction(path=path) for path in ensure_dirs),
        writes=tuple(writes),
    )

    payload = {
        "pane_kind": pane_kind,
        "branch": branch_data,
        "pane_manifest": manifest_data,
        "branch_path": str(branch_path.relative_to(entry.directory)),
        "pane_manifest_path": str(manifest_path.relative_to(entry.directory)),
    }
    if task_binding:
        payload["thread_metadata_updated"] = True

    return ThreadPlanResult(plans=(plan,), payload=payload)


def plan_migrate_singleton_branch(
    entry: ThreadEntry,
    *,
    pane_kind: str,
) -> ThreadPlanResult:
    sanitised_pane = _sanitize_pane_kind(pane_kind)
    legacy_branch_path = entry.directory / "branches" / f"{sanitised_pane}.json"
    legacy_manifest_path = entry.directory / "pane_manifests" / f"{sanitised_pane}.json"

    legacy_branch = _safe_load_json(legacy_branch_path) or {}
    legacy_manifest = _safe_load_json(legacy_manifest_path) or {}
    has_legacy = legacy_branch_path.exists() or legacy_manifest_path.exists()

    if not has_legacy:
        return ThreadPlanResult(
            plans=(),
            payload={
                "pane_kind": pane_kind,
                "migrated": False,
                "reason": "legacy_missing",
            },
        )

    branch_id = legacy_branch.get("branch_id") or legacy_branch.get("id") or legacy_manifest.get("branch_id")
    if branch_id is None:
        branch_id = uuid.uuid4().hex
    else:
        branch_id = _sanitize_branch_id(str(branch_id))

    branch_payload = dict(legacy_branch)
    branch_payload.setdefault("pane_kind", pane_kind)
    branch_payload["branch_id"] = branch_id
    branch_payload["id"] = branch_id
    branch_payload.setdefault("is_main", bool(branch_payload.get("is_main")))

    manifest_version = legacy_manifest.get("manifest_version", 1)
    manifest_payload = legacy_manifest.get("payload")
    pane_manifest = dict(legacy_manifest)
    if manifest_payload is None:
        pane_manifest["payload"] = {}

    base_plan = plan_branch_write(
        entry,
        function_name="branch-migrate",
        pane_kind=pane_kind,
        branch=branch_payload,
        pane_manifest=pane_manifest,
        manifest_version=manifest_version,
        task_binding=None,
    )
    plan = base_plan.plans[0]
    branch_path = (entry.directory / base_plan.payload["branch_path"]).resolve()
    manifest_path = (entry.directory / base_plan.payload["pane_manifest_path"]).resolve()

    moves: list[MoveInstruction] = list(plan.moves)
    if legacy_branch_path.exists() and legacy_branch_path.resolve() != branch_path:
        moves.append(MoveInstruction(src=legacy_branch_path, dest=branch_path, overwrite=True))
    if legacy_manifest_path.exists() and legacy_manifest_path.resolve() != manifest_path:
        moves.append(MoveInstruction(src=legacy_manifest_path, dest=manifest_path, overwrite=True))

    writes = []
    now = _iso_now()
    branch_metadata = {
        "process": entry.process_slug,
        "thread": entry.thread_slug,
        "pane": pane_kind,
    }
    writes.append(
        WriteInstruction(
            path=branch_path,
            content=json.dumps(base_plan.payload["branch"], indent=2) + "\n",
            policy=OperationWritePolicy.MODIFIABLE,
            event="updated",
            doc_type="thread-branch",
            timestamp=now,
            metadata=branch_metadata,
        )
    )
    writes.append(
        WriteInstruction(
            path=manifest_path,
            content=json.dumps(base_plan.payload["pane_manifest"], indent=2) + "\n",
            policy=OperationWritePolicy.MODIFIABLE,
            event="updated",
            doc_type="thread-pane-manifest",
            timestamp=now,
            metadata=branch_metadata,
        )
    )

    migrate_plan = OperationPlan(
        context=plan.context,
        ensure_dirs=plan.ensure_dirs,
        moves=tuple(moves),
        writes=tuple(writes),
    )

    payload = dict(base_plan.payload)
    payload["migrated"] = True

    return ThreadPlanResult(plans=(migrate_plan,), payload=payload)


def plan_participants_manifest(
    entry: ThreadEntry,
    *,
    function_name: str,
    manifest: ThreadParticipantsManifest,
) -> ThreadPlanResult:
    manifest_path = entry.directory / "participants.json"
    selectors = {
        "process": entry.process_slug,
        "thread": entry.thread_slug,
    }
    context = OperationContext(object_type="thread", function=function_name, selectors=selectors)

    manifest.updated_at = _iso_now()
    payload_dict = manifest.model_dump_json_ready()
    event = "created" if not manifest_path.exists() else "updated"

    plan = OperationPlan(
        context=context,
        ensure_dirs=(EnsureInstruction(path=manifest_path.parent),),
        writes=(
            WriteInstruction(
                path=manifest_path,
                content=json.dumps(payload_dict, indent=2) + "\n",
                policy=OperationWritePolicy.WRITE_ONCE if event == "created" else OperationWritePolicy.MODIFIABLE,
                event=event,
                doc_type="thread-participants",
                timestamp=manifest.updated_at,
                metadata={
                    "process": entry.process_slug,
                    "thread": entry.thread_slug,
                },
            ),
        ),
    )

    payload = {
        "manifest_path": str(manifest_path.relative_to(entry.directory)),
        "manifest": payload_dict,
    }
    return ThreadPlanResult(plans=(plan,), payload=payload)


__all__ = ["ThreadPlanResult", "plan_branch_write", "plan_participants_manifest"]
