from datetime import datetime, timezone
from pathlib import Path
from typing import Dict
import zipfile

import pytest

from aware_environment.fs import apply_plan
from aware_environments.kernel.objects.release import (
    bundle,
    locks_generate,
    manifest_validate,
    publish,
    secrets_list,
    terminal_refresh,
    terminal_validate,
    workflow_trigger,
)
from aware_release.bundle.manifest import load_manifest
from aware_release_pipeline.models import ProviderRefreshResult, ProviderValidationResult
from aware_release.workflows import WorkflowDispatchResult, WorkflowSpec


def test_release_locks_generate_plan(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    requirements_file = workspace_root / "requirements.txt"
    requirements_file.write_text("rich==13.7.0\nhttpx==0.27.0\n", encoding="utf-8")

    result = locks_generate(
        workspace_root,
        platform="linux-x86_64",
        requirements=[requirements_file],
        python_version="3.11",
        output_path=None,
    )

    apply_plan(result.plan)

    lock_path = workspace_root / "releases" / "locks" / "linux-x86_64.txt"
    assert lock_path.exists()

    content = lock_path.read_text(encoding="utf-8")
    assert "# aware-release lockfile" in content
    assert "rich" in content
    assert "httpx" in content


def _create_dummy_wheel(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("dummy/__init__.py", "__version__ = '0.0.1'\n")


def test_release_bundle_plan(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    wheel_path = tmp_path / "artifacts" / "dummy-0.0.1-py3-none-any.whl"
    _create_dummy_wheel(wheel_path)

    plan_result = bundle(
        workspace_root,
        channel="stable",
        version="0.0.1",
        platform="linux-x86_64",
        wheels=[wheel_path],
        dependencies=None,
        provider_paths=[],
        manifest_overrides=None,
        output_dir=None,
    )

    apply_plan(plan_result.plan)

    target_dir = workspace_root / "releases" / "stable" / "0.0.1" / "linux-x86_64"
    archive_path = target_dir / "aware-cli-stable-0.0.1-linux-x86_64.tar.gz"
    manifest_path = target_dir / "manifest.json"

    assert archive_path.exists()
    assert manifest_path.exists()


def test_release_publish_plan(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    wheel_path = tmp_path / "artifacts" / "dummy-0.0.1-py3-none-any.whl"
    _create_dummy_wheel(wheel_path)

    bundle_plan = bundle(
        workspace_root,
        channel="stable",
        version="0.0.1",
        platform="linux-x86_64",
        wheels=[wheel_path],
        dependencies=None,
        provider_paths=[],
        manifest_overrides=None,
        output_dir=None,
    )
    apply_plan(bundle_plan.plan)

    target_dir = workspace_root / "releases" / "stable" / "0.0.1" / "linux-x86_64"
    manifest_path = target_dir / "manifest.json"
    archive_path = target_dir / "aware-cli-stable-0.0.1-linux-x86_64.tar.gz"
    manifest = load_manifest(manifest_path)

    index_path = workspace_root / "releases" / "index.json"

    publish_plan = publish(
        workspace_root,
        manifest_path=manifest_path,
        archive_path=archive_path,
        manifest=manifest,
        url="https://example.com/artifacts/aware-cli.tar.gz",
        notes="Test release",
        dry_run=False,
        adapter_name="noop",
        adapter_options={},
        releases_index_path=index_path,
        signature_command=None,
        actor="test-agent",
    )

    apply_plan(publish_plan.plan)

    assert index_path.exists()
    data = index_path.read_text(encoding="utf-8")
    assert "stable" in data
    assert publish_plan.outcome.index_updated is True
    assert publish_plan.outcome.journal
    actions = {entry.action for entry in publish_plan.outcome.journal}
    assert "upload" in actions


def test_release_manifest_validate_success(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    wheel_path = tmp_path / "artifacts" / "dummy-0.0.1-py3-none-any.whl"
    _create_dummy_wheel(wheel_path)

    bundle_plan = bundle(
        workspace_root,
        channel="stable",
        version="0.0.1",
        platform="linux-x86_64",
        wheels=[wheel_path],
        dependencies=None,
        provider_paths=[],
        manifest_overrides=None,
        output_dir=None,
    )
    apply_plan(bundle_plan.plan)

    target_dir = workspace_root / "releases" / "stable" / "0.0.1" / "linux-x86_64"
    manifest_path = target_dir / "manifest.json"
    archive_path = target_dir / "aware-cli-stable-0.0.1-linux-x86_64.tar.gz"

    result = manifest_validate(
        workspace_root,
        manifest_path=manifest_path,
        archive_path=archive_path,
    )

    assert result.valid is True
    assert result.checksum_match is True
    assert result.manifest is not None
    assert result.manifest.channel == "stable"


def test_release_terminal_refresh_plan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    manifests_root = workspace_root / "libs" / "providers" / "terminal" / "aware_terminal_providers" / "providers"
    provider_dir = manifests_root / "demo"
    provider_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = provider_dir / "releases.json"
    manifest_path.write_text("{}\n", encoding="utf-8")

    def _fake_refresh(*, workspace_root: str | Path, manifests_dir: str | Path) -> ProviderRefreshResult:
        manifest_file = Path(manifests_dir) / "demo" / "releases.json"
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        manifest_file.write_text('{"versions": []}\n', encoding="utf-8")
        return ProviderRefreshResult(
            manifest_paths=[str(manifest_file)],
            providers_changed=["demo"],
            timestamp=datetime.now(timezone.utc),
            logs=["updated"],
        )

    monkeypatch.setattr(
        "aware_environments.kernel.objects.release.handlers.refresh_terminal_providers",
        _fake_refresh,
    )

    plan_result = terminal_refresh(workspace_root, manifests_dir=manifests_root)
    assert plan_result.payload["providers_changed"] == ["demo"]
    assert plan_result.plan.writes

    apply_plan(plan_result.plan)

    content = manifest_path.read_text(encoding="utf-8")
    assert "versions" in content


def test_release_terminal_validate_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    manifests_root = workspace_root / "providers"
    manifests_root.mkdir(parents=True, exist_ok=True)

    def _fake_validate(*, workspace_root: str | Path, manifests_dir: str | Path) -> ProviderValidationResult:
        return ProviderValidationResult(
            manifest_paths=[str(Path(manifests_dir) / "demo" / "releases.json")],
            issues=[],
            timestamp=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(
        "aware_environments.kernel.objects.release.handlers.validate_terminal_providers",
        _fake_validate,
    )

    payload = terminal_validate(workspace_root, manifests_dir=manifests_root)
    assert payload["manifest_paths"]
    assert payload["issues"] == []


def test_release_workflow_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = WorkflowSpec(slug="demo", repo="owner/repo", workflow="build.yml")

    def _fake_get_workflow(slug: str) -> WorkflowSpec:
        assert slug == "demo"
        return spec

    def _fake_dispatch(
        spec: WorkflowSpec,
        *,
        ref: str | None,
        inputs: Dict[str, str] | None,
        token_env_override: str | None,
        dry_run: bool,
        github_api: str,
    ) -> WorkflowDispatchResult:
        return WorkflowDispatchResult(
            status="dispatched" if not dry_run else "skipped",
            repo=spec.repo,
            workflow=spec.workflow,
            ref=ref or spec.ref,
            inputs=inputs or {},
            dry_run=dry_run,
            response_status=201,
            response_headers={},
        )

    monkeypatch.setattr(
        "aware_environments.kernel.objects.release.handlers.get_workflow",
        _fake_get_workflow,
    )
    monkeypatch.setattr(
        "aware_environments.kernel.objects.release.handlers.dispatch_workflow",
        _fake_dispatch,
    )

    payload = workflow_trigger(
        workflow="demo",
        inputs=["version=1.0.0"],
        ref="main",
        dry_run=True,
        github_api="https://api.example.com",
    )

    assert payload["dry_run"] is True
    assert payload["inputs"]["version"] == "1.0.0"


def test_release_secrets_list_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Secret:
        def __init__(self, name: str) -> None:
            self.name = name

    monkeypatch.setattr(
        "aware_environments.kernel.objects.release.handlers.list_secrets",
        lambda: [_Secret("one"), _Secret("two")],
    )
    monkeypatch.setattr(
        "aware_environments.kernel.objects.release.handlers.describe_secret",
        lambda name: {"name": name},
    )

    payload = secrets_list(name="two")
    assert payload == [{"name": "two"}]
