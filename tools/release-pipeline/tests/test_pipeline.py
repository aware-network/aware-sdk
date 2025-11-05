from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "release"))
sys.path.insert(0, str(ROOT / "tools" / "release-pipeline"))

from aware_release_pipeline.pipeline import prepare_release, publish_release
from aware_release_pipeline.pipelines import PipelineContext


def _create_wheel(path: Path, package: str, version: str) -> None:
    dist_info = f"{package}-{version}.dist-info"
    import zipfile

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{package}/__init__.py", "__version__ = \"{}\"\n".format(version))
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {package}\nVersion: {version}\n",
        )
        archive.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nGenerator: release-pipeline\nTag: py3-none-any\n")
        archive.writestr(f"{dist_info}/RECORD", "")


@pytest.fixture()
def sample_workspace(tmp_path: Path) -> Path:
    wheels_dir = tmp_path / "dist"
    wheels_dir.mkdir()
    cli_wheel = wheels_dir / "aware_cli-0.1.0-py3-none-any.whl"
    term_wheel = wheels_dir / "aware_terminal-0.2.0-py3-none-any.whl"
    _create_wheel(cli_wheel, "aware_cli", "0.1.0")
    _create_wheel(term_wheel, "aware_terminal", "0.2.0")
    providers_dir = tmp_path / "providers"
    providers_dir.mkdir()
    _create_wheel(providers_dir / "provider-1.0.0-py3-none-any.whl", "provider_pkg", "1.0.0")
    return tmp_path


def test_prepare_release_returns_bundle(sample_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = prepare_release(
        channel="dev",
        version="0.1.0",
        platform="linux-x86_64",
        wheels=["dist/aware_cli-0.1.0-py3-none-any.whl", "dist/aware_terminal-0.2.0-py3-none-any.whl"],
        output_dir="releases",
        providers_dir=["providers"],
        workspace_root=sample_workspace,
    )
    manifest_path = Path(payload.manifest_path)
    assert manifest_path.exists()
    archive_path = Path(payload.archive_path)
    assert archive_path.exists()


def test_publish_release_noop(sample_workspace: Path) -> None:
    prepare_release(
        channel="dev",
        version="0.1.0",
        platform="linux-x86_64",
        wheels=["dist/aware_cli-0.1.0-py3-none-any.whl"],
        output_dir="releases",
        workspace_root=sample_workspace,
    )
    payload = publish_release(
        channel="dev",
        version="0.1.0",
        platform="linux-x86_64",
        output_dir="releases",
        adapter="noop",
        workspace_root=sample_workspace,
        dry_run=True,
    )
    assert payload.upload.status == "skipped"


def test_cli_prepare(sample_workspace: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "aware_release_pipeline.cli",
        "cli",
        "prepare",
        "--channel",
        "dev",
        "--version",
        "0.1.0",
        "--platform",
        "linux-x86_64",
        "--wheel",
        "dist/aware_cli-0.1.0-py3-none-any.whl",
        "--output-dir",
        "releases",
        "--workspace-root",
        str(sample_workspace),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=_cli_env())
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "manifest_path" in data


def _cli_env() -> dict[str, str]:
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    extra_paths = [
        str(ROOT / "tools" / "release-pipeline"),
        str(ROOT / "tools" / "release"),
        str(ROOT / "tools" / "cli"),
    ]
    pythonpath = os.pathsep.join(extra_paths + ([current_pythonpath] if current_pythonpath else []))
    return {**os.environ, "PYTHONPATH": pythonpath}


def test_cli_workflow_list() -> None:
    cmd = [
        sys.executable,
        "-m",
        "aware_release_pipeline.cli",
        "workflow",
        "list",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=_cli_env())
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    slugs = {item["slug"] for item in payload}
    assert {"cli-release", "cli-rules-version"}.issubset(slugs)


def test_cli_workflow_trigger_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_TOKEN_RELEASE", raising=False)
    for slug in ("cli-release", "cli-rules-version"):
        cmd = [
            sys.executable,
            "-m",
            "aware_release_pipeline.cli",
            "workflow",
            "trigger",
            "--workflow",
            slug,
            "--input",
            "version=0.1.0",
            "--dry-run",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=_cli_env())
        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        assert payload["status"] == "skipped"


def test_cli_rules_render(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    called: dict[str, object] = {}

    from aware_release_pipeline.models import RulesRenderResult

    def fake_render_rules(**kwargs):
        called.update(kwargs)
        return RulesRenderResult(
            cli_version=kwargs.get("version") or "1.2.3",
            rules_root=str(kwargs.get("rules_root", "custom/rules")),
            manifest_path=str(kwargs.get("manifest_path", "output/manifest.json")),
            rules=["alpha"],
            update_current=kwargs.get("update_current", "copy"),
        )

    import aware_release_pipeline.cli as pipeline_cli

    monkeypatch.setattr(pipeline_cli, "render_rules", fake_render_rules)

    exit_code = pipeline_cli.main(
        [
            "rules",
            "render",
            "--version",
            "1.2.3",
            "--rules-root",
            "custom/rules",
            "--manifest",
            "output/manifest.json",
            "--workspace-root",
            str(tmp_path),
            "--keep-manifest",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["cli_version"] == "1.2.3"
    assert payload["manifest_path"].endswith("output/manifest.json")
    assert payload["rules"] == ["alpha"]
    assert called["version"] == "1.2.3"
    assert called["rules_root"] == "custom/rules"
    assert called["manifest_path"] == "output/manifest.json"
    assert called["workspace_root"] == str(tmp_path)


def _touch_file(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_cli_sdk_sync(tmp_path: Path) -> None:
    export_root = tmp_path / "export"
    target_root = tmp_path / "target"
    export_root.mkdir()
    target_root.mkdir()
    (target_root / ".git").mkdir()

    _touch_file(export_root / "README.md", "export readme")
    _touch_file(export_root / "dir" / "file.txt", "hello")
    _touch_file(target_root / "obsolete.txt", "remove me")

    cmd = [
        sys.executable,
        "-m",
        "aware_release_pipeline.cli",
        "sdk",
        "sync",
        "--export-root",
        str(export_root),
        "--target",
        str(target_root),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=_cli_env())
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["status"] == "synced"
    assert (target_root / ".git").exists()
    assert not (target_root / "obsolete.txt").exists()
    assert (target_root / "dir" / "file.txt").read_text(encoding="utf-8") == "hello"

    dry_cmd = cmd + ["--dry-run"]
    proc_dry = subprocess.run(dry_cmd, capture_output=True, text=True, check=False, env=_cli_env())
    assert proc_dry.returncode == 0
    dry_payload = json.loads(proc_dry.stdout)
    assert dry_payload["status"] == "dry_run"


def test_cli_sdk_publish(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    target_root = tmp_path / "target"
    target_root.mkdir()
    (target_root / ".git").mkdir()

    class FakeResult:
        status = "ok"
        artifacts: dict[str, object] = {}
        receipts: dict[str, object] = {}
        logs: list[str] = []
        next_steps: list[str] = []
        data = {"version": {"new": "0.5.1"}}

    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_pipeline(**kwargs):
        return FakeResult()

    def fake_sync(export_root: str, target_root: str, dry_run: bool) -> dict[str, object]:
        calls.append((("sync",), Path(target_root)))
        return {"status": "synced"}

    def fake_git(args, *, cwd, capture_output=False):
        calls.append((tuple(args), Path(cwd)))
        if args and args[0] == "git" and "status" in args:
            return SimpleNamespace(stdout=" M README.md\n")
        if args and args[0] == "git" and "rev-parse" in args:
            return SimpleNamespace(stdout="abc123\n")
        return SimpleNamespace(stdout="")

    import aware_release_pipeline.cli as pipeline_cli

    monkeypatch.setattr(pipeline_cli, "_run_sdk_pipeline", fake_pipeline)
    monkeypatch.setattr(pipeline_cli, "_sync_sdk_export", fake_sync)
    monkeypatch.setattr(pipeline_cli, "_run_git_command", fake_git)

    payload = pipeline_cli._publish_sdk_export(
        workspace_root=str(tmp_path),
        target_root=str(target_root),
        branch="main",
        skip_versioning=True,
        skip_workflow=True,
        pipeline_dry_run=False,
        skip_push=False,
        commit_message=None,
    )
    assert payload["status"] == "ok"
    assert payload["version"] == "0.5.1"
    assert payload["message"] == "chore: sync aware-sdk 0.5.1"
    assert payload["commit"] == "abc123"
    assert payload["pushed"] is True

    git_commands = [call[0] for call in calls if call[0][0] == "git"]
    assert ("git", "checkout", "main") in git_commands
    assert ("git", "add", "-A") in git_commands
    assert ("git", "commit", "-m", "chore: sync aware-sdk 0.5.1") in git_commands
    assert ("git", "push", "origin", "main") in git_commands


def test_terminal_release_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import aware_release_pipeline.pipelines as pipelines_mod

    build_calls: list[dict] = []
    test_calls: list[dict] = []

    def fake_build(**kwargs):
        build_calls.append(kwargs)
        return ["dist/fake.whl"], {"status": "ok"}

    def fake_tests(command, cwd):
        test_calls.append({"command": command, "cwd": cwd})
        return {"command": command, "returncode": 0, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(pipelines_mod, "_run_uv_build", fake_build)
    monkeypatch.setattr(pipelines_mod, "_run_release_tests", fake_tests)

    context = PipelineContext(workspace_root=tmp_path, inputs={}, raw_inputs={})
    result = pipelines_mod._pipeline_terminal_release(context)

    assert result.status == "ok"
    assert len(build_calls) == 2
    assert len(test_calls) == 2
    assert "aware-terminal" in result.receipts
    assert "aware-terminal-providers" in result.receipts
    assert "aware-terminal-control-center" not in result.receipts


def test_terminal_release_with_control_center(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import aware_release_pipeline.pipelines as pipelines_mod

    build_calls: list[dict] = []
    test_calls: list[dict] = []

    def fake_build(**kwargs):
        build_calls.append(kwargs)
        return ["dist/fake.whl"], {"status": "ok"}

    def fake_tests(command, cwd):
        test_calls.append({"command": command, "cwd": cwd})
        return {"command": command, "returncode": 0, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(pipelines_mod, "_run_uv_build", fake_build)
    monkeypatch.setattr(pipelines_mod, "_run_release_tests", fake_tests)

    context = PipelineContext(
        workspace_root=tmp_path,
        inputs={"include-control-center": True},
        raw_inputs={},
    )
    result = pipelines_mod._pipeline_terminal_release(context)

    assert result.status == "ok"
    assert len(build_calls) == 3
    assert len(test_calls) == 3
    assert "aware-terminal-control-center" in result.receipts


def test_cli_pipeline_list() -> None:
    cmd = [
        sys.executable,
        "-m",
        "aware_release_pipeline.cli",
        "pipeline",
        "list",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=_cli_env())
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    slugs = {item["slug"] for item in payload}
    assert {
        "tests-release",
        "file-system-release",
        "sdk-release",
        "cli-bundle",
        "cli-rules",
        "terminal-providers",
        "cli-release-e2e",
    }.issubset(slugs)


def test_cli_pipeline_run_cli_bundle(sample_workspace: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "aware_release_pipeline.cli",
        "pipeline",
        "run",
        "--pipeline",
        "cli-bundle",
        "--input",
        "channel=dev",
        "--input",
        "version=0.1.0",
        "--input",
        "wheel=dist/aware_cli-0.1.0-py3-none-any.whl",
        "--input",
        "wheel=dist/aware_terminal-0.2.0-py3-none-any.whl",
        "--workspace-root",
        str(sample_workspace),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=_cli_env())
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["status"] == "ok"
    assert "archive" in payload["artifacts"]
    assert payload["artifacts"]["archive"].endswith(".tar.gz")


def test_pipeline_cli_release_e2e(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aware_release.workflows import WorkflowDispatchResult
    import aware_release_pipeline.pipelines as pipelines_mod
    from aware_release_pipeline.pipelines import PipelineContext, PipelineResult

    order: list[str] = []

    def fake_read_version(cfg):
        order.append('read-version')
        return '0.1.0'

    def fake_bump_version(version, bump):
        order.append('bump-version')
        return '0.1.1'

    def fake_write_version(cfg, version):
        order.append('write-version')

    def fake_update_changelog(cfg, version, ts, summary):
        order.append('changelog')
        return 'entry'

    def fake_uv_build(**kwargs):
        order.append("build")
        return ["dist/built.whl"], {
            "status": "ok",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "wheels": ["dist/built.whl"],
        }

    def fake_bundle(context):
        order.append("bundle")
        return PipelineResult(
            status="ok",
            artifacts={"archive": "bundle.tar.gz", "manifest": "manifest.json"},
            data={"prepare": {"manifest_path": "manifest.json"}},
        )

    def fake_rules(context):
        order.append("rules")
        return PipelineResult(
            status="ok",
            artifacts={"manifest": "rules.json"},
            data={"rules": {"manifest_path": "rules.json"}},
        )

    def fake_tests(command, cwd, env=None):
        order.append("tests")
        assert command[0:2] == ["uv", "run"]
        assert "aware-tests" in command
        assert cwd == tmp_path
        return {"command": command, "returncode": 0, "stdout": "ok", "stderr": ""}

    def fake_trigger(*args, **kwargs):
        order.append("workflow")
        return WorkflowDispatchResult(
            status="dispatched",
            repo="repo",
            workflow="wf",
            ref="main",
            inputs={},
            dry_run=False,
            response_status=204,
        )

    def fake_publish(**kwargs):
        order.append("publish")
        return {"built": ["dist/aware_release-0.1.2-py3-none-any.whl"], "published": True}

    monkeypatch.setattr(pipelines_mod, "read_version", fake_read_version)
    monkeypatch.setattr(pipelines_mod, "bump_version", fake_bump_version)
    monkeypatch.setattr(pipelines_mod, "write_version", fake_write_version)
    monkeypatch.setattr(pipelines_mod, "update_changelog", fake_update_changelog)
    monkeypatch.setattr(pipelines_mod, "_run_uv_build", fake_uv_build)
    monkeypatch.setattr(pipelines_mod, "_pipeline_cli_bundle", fake_bundle)
    monkeypatch.setattr(pipelines_mod, "_pipeline_rules_version", fake_rules)
    monkeypatch.setattr(pipelines_mod, "_run_release_tests", fake_tests)
    monkeypatch.setattr(pipelines_mod, "trigger_workflow", fake_trigger)
    monkeypatch.setattr(pipelines_mod, "publish_awarerelease_pypi", fake_publish)

    context = PipelineContext(
        workspace_root=tmp_path,
        inputs={
            "channel": "dev",
            "version": "0.1.2",
            "platform": "linux-x86_64",
        },
        raw_inputs={},
    )

    result = pipelines_mod._pipeline_cli_release_e2e(context)

    assert result.status == "ok"
    assert order == ["read-version", "bump-version", "write-version", "changelog", "build", "bundle", "rules", "tests", "workflow", "publish"]
    assert result.receipts["build"]["status"] == "ok"
    assert result.receipts["version"]["new"] == "0.1.1"
    assert result.receipts["bundle"]["prepare"]["manifest_path"] == "manifest.json"
    assert result.receipts["workflow"]["status"] == "ok"
    assert result.receipts["publish"]["status"] == "ok"
    assert result.artifacts["wheels"] == ["dist/built.whl"]


def test_cli_terminal_refresh(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from aware_release_pipeline.models import ProviderRefreshResult
    import aware_release_pipeline.cli as pipeline_cli

    def fake_refresh(**kwargs):
        return ProviderRefreshResult(
            manifest_paths=["providers/codex/releases.json"],
            providers_changed=["codex"],
            timestamp=datetime.now(timezone.utc),
            logs=["refreshed"],
        )

    monkeypatch.setattr("aware_release_pipeline.cli.refresh_terminal_providers", fake_refresh)

    exit_code = pipeline_cli.main(
        [
            "terminal",
            "refresh",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["providers_changed"] == ["codex"]


def test_cli_terminal_validate(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from aware_release_pipeline.models import ProviderValidationResult, ProviderValidationIssue
    import aware_release_pipeline.cli as pipeline_cli

    def fake_validate(**kwargs):
        return ProviderValidationResult(
            manifest_paths=["providers/codex/releases.json"],
            issues=[ProviderValidationIssue(manifest="providers/codex/releases.json", message="bad", level="error")],
            timestamp=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("aware_release_pipeline.cli.validate_terminal_providers", fake_validate)

    exit_code = pipeline_cli.main(
        [
            "terminal",
            "validate",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    payload = json.loads(captured.out)
    assert payload["issues"][0]["message"] == "bad"


def test_cli_aware_release_publish_pypi(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_publish(**kwargs):
        return {
            "built": ["dist/aware_release-0.1.1-py3-none-any.whl"],
            "published": not kwargs.get("dry_run", False),
            "repository": kwargs.get("repository", "pypi"),
            "logs": ["stub"],
        }

    import aware_release_pipeline.cli as pipeline_cli

    monkeypatch.setattr(pipeline_cli, "publish_awarerelease_pypi", fake_publish)

    repo_root = Path(__file__).resolve().parents[3]
    pyproject_path = repo_root / "tools" / "release" / "pyproject.toml"

    exit_code = pipeline_cli.main(
        [
            "cli",
            "aware-release",
            "publish-pypi",
            "--dry-run",
            "--pyproject",
            str(pyproject_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["published"] is False
