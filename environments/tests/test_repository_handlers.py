from __future__ import annotations

import json
from pathlib import Path

from aware_environment.fs import apply_plan
from aware_environment.fs.receipt import Receipt, WriteOp
from aware_environments.kernel.objects.repository.handlers import (
    list_repositories,
    repository_index_refresh,
    repository_status,
)


def _bootstrap_repository(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "src").mkdir(parents=True, exist_ok=True)
    (repo_root / ".aware").mkdir()
    (repo_root / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
    (repo_root / "src" / "main.py").write_text("print('hello world')\n", encoding="utf-8")
    return repo_root


def test_repository_index_refresh_creates_index(tmp_path: Path) -> None:
    repo_root = _bootstrap_repository(tmp_path)

    result = repository_index_refresh(repo_root)
    receipt = apply_plan(result.plan)
    assert isinstance(receipt, Receipt)
    assert any(isinstance(op, WriteOp) and op.doc_type == "repository-index" for op in receipt.fs_ops)

    index_path = repo_root / ".aware" / "index" / "repository_index.json"
    assert index_path.exists()

    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(data) == result.entry_count
    assert data[0]["workspace_root"] == str(repo_root.resolve())


def test_repository_status_returns_index_payload(tmp_path: Path) -> None:
    repo_root = _bootstrap_repository(tmp_path)
    receipt = apply_plan(repository_index_refresh(repo_root).plan)
    assert isinstance(receipt, Receipt)
    assert any(isinstance(op, WriteOp) and op.doc_type == "repository-index" for op in receipt.fs_ops)

    payload = repository_status(repo_root)
    assert payload["workspace_root"] == str(repo_root.resolve())
    assert payload["index_path"].endswith("repository_index.json")
    assert "repository_id" in payload
    assert "metadata" in payload


def test_list_repositories_reads_index(tmp_path: Path) -> None:
    repo_root = _bootstrap_repository(tmp_path)
    apply_plan(repository_index_refresh(repo_root).plan)

    entries = list_repositories(repo_root)
    assert entries, "Expected repository entries"
    assert entries[0]["workspace_root"] == str(repo_root.resolve())
