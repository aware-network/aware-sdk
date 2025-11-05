from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pytest

from aware_environment.fs import (
    EnsureInstruction,
    MoveInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    PolicyAdapter,
    WriteInstruction,
    apply_plan,
)


class _TrackingAdapter(PolicyAdapter):
    def __init__(self) -> None:
        self.created: list[Path] = []
        self.appended: list[Path] = []
        self.modified: list[Path] = []
        self.hook_calls: list[Mapping[str, object]] = []

    def guard_create(self, path: Path, *, force: bool = False) -> None:
        self.created.append(path)

    def guard_append(self, path: Path) -> None:
        self.appended.append(path)

    def guard_modify(self, path: Path) -> None:
        self.modified.append(path)

    def build_receipt(self, action: str, path: Path, metadata: Mapping[str, object] | None = None) -> object:
        return {"action": action, "path": str(path), "metadata": dict(metadata or {})}

    def run_hooks(self, receipt: object) -> None:
        assert isinstance(receipt, dict)
        self.hook_calls.append(receipt.get("metadata", {}))


def _plan_for_path(path: Path, *, policy: OperationWritePolicy) -> OperationPlan:
    context = OperationContext(object_type="task", function="design", selectors={"task": "demo"})
    timestamp = datetime.now(timezone.utc)
    frontmatter = "---\nid: demo\ntitle: demo\n---\n\nBody\n"
    write = WriteInstruction(
        path=path,
        content=frontmatter,
        policy=policy,
        event="created",
        doc_type="design",
        timestamp=timestamp,
        metadata={"id": "demo", "title": "demo"},
        hook_metadata={},
    )
    ensure_dir = EnsureInstruction(path=path.parent)
    return OperationPlan(context=context, ensure_dirs=(ensure_dir,), writes=(write,))


def test_apply_plan_creates_file(tmp_path: Path) -> None:
    plan = _plan_for_path(tmp_path / "foo.md", policy=OperationWritePolicy.WRITE_ONCE)
    receipt = apply_plan(plan)

    target = tmp_path / "foo.md"
    assert target.exists()
    assert receipt.context.object_type == "task"
    assert len(receipt.fs_ops) == 2
    assert receipt.fs_ops[0].type == "ensure"
    assert receipt.fs_ops[1].type == "write"
    assert receipt.fs_ops[1].path == target


def test_apply_plan_write_once_requires_force(tmp_path: Path) -> None:
    target = tmp_path / "foo.md"
    target.write_text("existing", encoding="utf-8")
    plan = _plan_for_path(target, policy=OperationWritePolicy.WRITE_ONCE)

    with pytest.raises(FileExistsError):
        apply_plan(plan)


def test_apply_plan_modifiable_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "foo.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old", encoding="utf-8")

    plan = _plan_for_path(target, policy=OperationWritePolicy.MODIFIABLE)
    apply_plan(plan)

    assert target.read_text(encoding="utf-8").startswith("---")


def test_apply_plan_dry_run_does_not_mutate(tmp_path: Path) -> None:
    plan = _plan_for_path(tmp_path / "foo.md", policy=OperationWritePolicy.WRITE_ONCE)
    receipt = apply_plan(plan, dry_run=True)

    assert not (tmp_path / "foo.md").exists()
    assert not receipt.fs_ops


def test_apply_plan_uses_custom_policy_adapter(tmp_path: Path) -> None:
    target = tmp_path / "foo.md"
    adapter = _TrackingAdapter()

    plan = _plan_for_path(target, policy=OperationWritePolicy.WRITE_ONCE)

    def provider(_: WriteInstruction) -> PolicyAdapter:
        return adapter

    apply_plan(plan, policy_provider=provider)

    assert adapter.created == [target]
    assert adapter.hook_calls == [{}]
