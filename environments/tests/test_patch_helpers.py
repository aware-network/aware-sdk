from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from aware_environment.fs import OperationWritePolicy
from aware_environments.kernel.objects._shared.patch import build_patch_instruction_from_text


def test_build_patch_instruction_from_text_returns_diff(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    timestamp = datetime.now(timezone.utc)

    instruction, diff_text = build_patch_instruction_from_text(
        path=path,
        original_text="line1\nline2\n",
        updated_text="line1\nlineX\n",
        doc_type="test-doc",
        timestamp=timestamp,
        policy=OperationWritePolicy.MODIFIABLE,
        metadata={"path": str(path)},
        summary="Updated line",
        event="modified",
    )

    assert instruction is not None
    assert diff_text
    assert instruction.doc_type == "test-doc"
    assert instruction.policy is OperationWritePolicy.MODIFIABLE
    assert instruction.summary == "Updated line"
    assert instruction.hook_metadata.get("summary") == "Updated line"
    assert "-line2" in instruction.diff
    assert "+lineX" in instruction.diff


def test_build_patch_instruction_from_text_no_change_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    timestamp = datetime.now(timezone.utc)

    instruction, diff_text = build_patch_instruction_from_text(
        path=path,
        original_text="content\n",
        updated_text="content\n",
        doc_type="test-doc",
        timestamp=timestamp,
        policy=OperationWritePolicy.MODIFIABLE,
        metadata={"path": str(path)},
    )

    assert instruction is None
    assert diff_text == ""

