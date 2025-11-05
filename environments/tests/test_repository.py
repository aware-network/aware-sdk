from pathlib import Path

from aware_environment.fs import apply_plan
from aware_environments.kernel.objects.repository import (
    RepositoryFSAdapter,
    RepositoryIndexPlanResult,
    repository_index_refresh,
    repository_status,
)


def _prepare_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("# Repo\n", encoding="utf-8")
    (repo / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    return repo


def test_repository_fs_adapter_roundtrip(tmp_path: Path) -> None:
    repo_root = _prepare_repo(tmp_path)
    adapter = RepositoryFSAdapter(repo_root)
    entries = adapter.build_index()
    assert entries and entries[0].workspace_root == str(repo_root.resolve())
    index_path = adapter.write_index(entries)
    assert index_path.exists()
    reloaded = adapter.read_index()
    assert len(reloaded) == len(entries)


def test_repository_handlers(tmp_path: Path) -> None:
    repo_root = _prepare_repo(tmp_path)
    result = repository_index_refresh(repo_root)
    assert isinstance(result, RepositoryIndexPlanResult)
    apply_plan(result.plan)
    assert result.entry_count == 1
    status = repository_status(repo_root)
    assert status["workspace_root"] == str(repo_root.resolve())
    assert "index_path" in status
