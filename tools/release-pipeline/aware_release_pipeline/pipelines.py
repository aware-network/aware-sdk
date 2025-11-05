from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from .pipeline import (
    prepare_release,
    publish_awarerelease_pypi,
    render_rules,
    refresh_terminal_providers,
    validate_terminal_providers,
)
from .versioning import (
    VersionConfig,
    bump_version,
    read_version,
    update_changelog,
    write_version,
)
from .workflows import get_workflow
from aware_release.workflows import WorkflowTriggerError, trigger_workflow


SDK_EXPORT_BASE_DIRS = ["aware_sdk", "tests", ".github"]
SDK_EXPORT_BASE_FILES = [".gitignore", "pyproject.toml", "README.md", "CHANGELOG.md", "LICENSE", "uv.lock"]
SDK_EXPORT_ENTRIES = [
    ("libs/file_system", "libs/file_system"),
    ("libs/environment", "libs/environment"),
    ("tools/release", "tools/release"),
    ("tools/release-pipeline", "tools/release-pipeline"),
    ("tools/test-runner", "tools/test-runner"),
    ("tools/terminal", "tools/terminal"),
    ("libs/providers/terminal", "libs/providers/terminal"),
]


class PipelineError(RuntimeError):
    """Raised when a pipeline execution fails validation or runtime checks."""


@dataclass(frozen=True)
class PipelineInputSpec:
    description: Optional[str] = None
    default: Optional[object] = None
    required: bool = False
    multiple: bool = False

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "description": self.description,
            "required": self.required,
            "multiple": self.multiple,
        }
        if self.default is not None:
            payload["default"] = self.default
        return payload


@dataclass(frozen=True)
class PipelineSpec:
    slug: str
    description: str
    runner: Callable[["PipelineContext"], "PipelineResult"]
    inputs: Dict[str, PipelineInputSpec] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    receipts: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "slug": self.slug,
            "description": self.description,
            "inputs": {name: spec.to_dict() for name, spec in self.inputs.items()},
            "artifacts": list(self.artifacts),
            "receipts": list(self.receipts),
        }


@dataclass
class PipelineContext:
    workspace_root: Path
    inputs: Dict[str, object]
    raw_inputs: Dict[str, List[str]]

    def get(self, name: str, default: Optional[object] = None) -> Optional[object]:
        return self.inputs.get(name, default)

    def get_list(self, name: str) -> List[str]:
        value = self.inputs.get(name)
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value]
        return [str(value)]


@dataclass
class PipelineResult:
    status: str = "ok"
    artifacts: Dict[str, object] = field(default_factory=dict)
    receipts: Dict[str, object] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    data: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "artifacts": self.artifacts,
            "receipts": self.receipts,
            "logs": self.logs,
            "next_steps": self.next_steps,
            "data": self.data,
        }


_PIPELINES: Dict[str, PipelineSpec] = {}


def register_pipeline(spec: PipelineSpec) -> None:
    if spec.slug in _PIPELINES:
        raise ValueError(f"Pipeline '{spec.slug}' already registered.")
    _PIPELINES[spec.slug] = spec


def get_pipeline(slug: str) -> PipelineSpec:
    try:
        return _PIPELINES[slug]
    except KeyError as exc:
        available = ", ".join(sorted(_PIPELINES))
        raise KeyError(f"Unknown pipeline slug '{slug}'. Available pipelines: {available}.") from exc


def list_pipelines() -> Iterable[PipelineSpec]:
    return _PIPELINES.values()


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _clean_list(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _parse_key_value_pairs(values: List[str]) -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    for entry in values:
        if "=" not in entry:
            raise PipelineError(f"Expected key=value format (got '{entry}')")
        key, raw_value = entry.split("=", 1)
        key = key.strip()
        if not key:
            raise PipelineError("Key cannot be empty in key=value input.")
        pairs[key] = raw_value.strip()
    return pairs


def _run_uv_build(
    *,
    workspace_root: Path,
    project: str,
    out_dir: str,
    extra_args: List[str],
    env: Optional[Dict[str, str]] = None,
) -> tuple[List[str], Dict[str, object]]:
    project_path = Path(project)
    if not project_path.is_absolute():
        project_path = workspace_root / project_path
    if not project_path.exists():
        raise PipelineError(f"Build project path not found: {project_path}")

    out_path = Path(out_dir)
    if not out_path.is_absolute():
        out_path = workspace_root / out_path
    out_path.mkdir(parents=True, exist_ok=True)

    command = [
        "uv",
        "build",
        "--project",
        str(project_path),
        "--wheel",
        "--out-dir",
        str(out_path),
    ]
    command.extend(str(arg) for arg in extra_args)

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    result = subprocess.run(
        command,
        cwd=str(project_path),
        capture_output=True,
        text=True,
        env=merged_env,
    )
    if result.returncode != 0:
        raise PipelineError(f"uv build failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}")

    wheels = sorted(out_path.glob("*.whl"))
    if not wheels:
        raise PipelineError(f"No wheels produced in {out_path}")

    resolved: List[str] = []
    for wheel in wheels:
        try:
            resolved.append(str(wheel.relative_to(workspace_root)))
        except ValueError:
            resolved.append(str(wheel))
    receipt = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project": str(project_path),
        "out_dir": str(out_path),
        "command": command,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "wheels": resolved,
    }
    return resolved, receipt


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".venv",
            ".git",
            ".eggs",
            "*.egg-info",
        ),
    )


def _stage_sdk_sources(workspace_root: Path) -> Path:
    source_root = workspace_root / "apps" / "aware-sdk"
    staging_root = workspace_root / "build" / "sdk-export"

    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)

    for relative_dir in SDK_EXPORT_BASE_DIRS:
        src_dir = source_root / relative_dir
        if src_dir.exists():
            _copy_tree(src_dir, staging_root / relative_dir)

    for relative_file in SDK_EXPORT_BASE_FILES:
        src_file = source_root / relative_file
        if src_file.exists():
            dst_file = staging_root / relative_file
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)

    for src_rel, dst_rel in SDK_EXPORT_ENTRIES:
        src_path = workspace_root / src_rel
        if not src_path.exists():
            raise PipelineError(f"SDK export source missing: {src_path}")
        dst_path = staging_root / dst_rel
        _copy_tree(src_path, dst_path)

    return staging_root


def _pipeline_cli_bundle(context: PipelineContext) -> PipelineResult:
    channel = context.get("channel")
    version = context.get("version")
    wheels = _clean_list(context.get("wheel"))

    if not channel:
        raise PipelineError("Pipeline 'cli-bundle' requires --input channel=<name>.")
    if not version:
        raise PipelineError("Pipeline 'cli-bundle' requires --input version=<semver>.")
    if not wheels:
        raise PipelineError("Pipeline 'cli-bundle' requires at least one --input wheel=<path>.")

    platform = context.get("platform") or "linux-x86_64"
    output_dir = context.get("output-dir") or "releases"
    providers_dir = _clean_list(context.get("providers-dir"))
    provider_wheels = _clean_list(context.get("provider-wheel"))
    overrides = _clean_list(context.get("manifest-override"))
    dependencies_file = context.get("dependencies-file")
    generate_lock = _to_bool(context.get("generate-lock"))
    lock_output = context.get("lock-output")
    python_version = context.get("python-version")

    prepare_result = prepare_release(
        channel=str(channel),
        version=str(version),
        platform=str(platform),
        wheels=[str(path) for path in wheels],
        output_dir=str(output_dir),
        providers_dir=[str(path) for path in providers_dir] or None,
        provider_wheels=[str(path) for path in provider_wheels] or None,
        dependencies_file=str(dependencies_file) if dependencies_file else None,
        manifest_overrides=[str(item) for item in overrides] or None,
        generate_lockfile=generate_lock,
        lock_output=str(lock_output) if lock_output else None,
        python_version=str(python_version) if python_version else None,
        workspace_root=context.workspace_root,
    )

    artifacts: Dict[str, object] = {
        "archive": prepare_result.archive_path,
        "manifest": prepare_result.manifest_path,
    }
    if prepare_result.lock_path:
        artifacts["lock"] = prepare_result.lock_path

    return PipelineResult(
        status="ok",
        artifacts=artifacts,
        data={"prepare": prepare_result.to_dict()},
    )


def _pipeline_rules_version(context: PipelineContext) -> PipelineResult:
    keep_manifest = _to_bool(context.get("keep-manifest"))
    rules_root = context.get("rules-root") or "docs/rules"
    manifest_path = context.get("manifest") or "build/rule-manifest.json"
    update_current = context.get("update-current") or "copy"

    render_result = render_rules(
        version=str(context.get("version")) if context.get("version") else None,
        rules_root=str(rules_root),
        manifest_path=str(manifest_path),
        update_current=str(update_current),
        workspace_root=context.workspace_root,
        clean_manifest=not keep_manifest,
    )

    artifacts = {
        "manifest": render_result.manifest_path,
        "rules_root": render_result.rules_root,
    }

    return PipelineResult(
        status="ok",
        artifacts=artifacts,
        data={"rules": render_result.to_dict()},
    )


def _pipeline_terminal_providers(context: PipelineContext) -> PipelineResult:
    manifests_dir = context.get("manifests-dir") or "libs/providers/terminal/aware_terminal_providers/providers"
    skip_refresh = _to_bool(context.get("skip-refresh"))

    refresh_result = None
    logs: List[str] = []

    if not skip_refresh:
        refresh_result = refresh_terminal_providers(
            workspace_root=context.workspace_root,
            manifests_dir=str(manifests_dir),
        )
        logs.extend(refresh_result.logs)

    validation_result = validate_terminal_providers(
        workspace_root=context.workspace_root,
        manifests_dir=str(manifests_dir),
    )

    issues_present = bool(validation_result.issues)
    if issues_present:
        logs.append(
            "Validation detected provider issues: "
            + "; ".join(f"{issue.manifest}: {issue.message}" for issue in validation_result.issues)
        )

    data = {
        "refresh": refresh_result.to_dict() if refresh_result else None,
        "validation": validation_result.to_dict(),
    }

    next_steps: List[str] = []
    if issues_present:
        next_steps.append("Resolve provider manifest validation issues before publishing.")

    return PipelineResult(
        status="error" if issues_present else "ok",
        artifacts={"manifests": validation_result.manifest_paths},
        logs=logs,
        next_steps=next_steps,
        data=data,
    )


def _run_release_tests(command: List[str], *, cwd: Path, env: Optional[Dict[str, str]] = None) -> Dict[str, object]:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
    )
    result = {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    if proc.returncode != 0:
        snippet_stdout = proc.stdout[-2000:] if proc.stdout else ""
        snippet_stderr = proc.stderr[-2000:] if proc.stderr else ""
        message = (
            "Aware test suite failed; see stdout/stderr for details.\n"
            "--- stdout (tail) ---\n"
            f"{snippet_stdout}\n"
            "--- stderr (tail) ---\n"
            f"{snippet_stderr}\n"
        )
        raise PipelineError(message)
    return result


def _pipeline_cli_release_e2e(context: PipelineContext) -> PipelineResult:
    logs: List[str] = []
    receipts: Dict[str, object] = {}
    artifacts: Dict[str, object] = {}
    workspace_root = context.workspace_root

    bump_type = str(context.get("bump") or "patch")
    skip_versioning = _to_bool(context.get("skip-versioning"))
    dry_run = _to_bool(context.get("dry-run"))
    timestamp = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp_iso = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    version_config = VersionConfig.from_project(
        project_root=workspace_root / "tools" / "release",
        module_relpath="aware_release/__init__.py",
        changelog="CHANGELOG.md",
    )
    previous_version = read_version(version_config)
    new_version = previous_version
    changelog_entry = None

    if not skip_versioning:
        new_version = bump_version(previous_version, bump_type)
        if not dry_run:
            write_version(version_config, new_version)
            summary_lines = context.get_list("changelog-entry")
            changelog_entry = update_changelog(
                version_config,
                new_version,
                timestamp,
                [line for line in summary_lines if line],
            )

    context.inputs["version"] = new_version
    receipts["version"] = {
        "previous": previous_version,
        "new": new_version,
        "bump": bump_type,
        "timestamp": timestamp_iso,
        "changelog": str(version_config.changelog_path),
        "changelog_entry": changelog_entry,
        "skip_versioning": skip_versioning,
    }

    skip_build = _to_bool(context.get("skip-build"))
    build_receipt: Dict[str, object]
    built_wheels: List[str] = []
    if skip_build:
        build_receipt = {
            "status": "skipped",
            "reason": "skip-build flag enabled",
            "timestamp": timestamp_iso,
        }
    else:
        build_project = context.get("build-project") or "tools/cli"
        build_out_dir = context.get("build-out-dir") or "dist"
        build_args = context.get_list("build-arg")
        built_wheels, build_receipt = _run_uv_build(
            workspace_root=workspace_root,
            project=str(build_project),
            out_dir=str(build_out_dir),
            extra_args=[str(arg) for arg in build_args],
        )
        if build_receipt.get("stdout"):
            logs.append(str(build_receipt["stdout"]))
        if build_receipt.get("stderr"):
            logs.append(str(build_receipt["stderr"]))
    receipts["build"] = build_receipt

    manual_wheels = [wheel for wheel in context.get_list("wheel") if wheel]
    final_wheels = built_wheels + manual_wheels
    if not final_wheels:
        raise PipelineError("No wheels available for bundle step; build or provide --input wheel=...")
    artifacts["wheels"] = final_wheels

    bundle_inputs = dict(context.inputs)
    bundle_inputs["wheel"] = final_wheels
    bundle_context = PipelineContext(
        workspace_root=workspace_root,
        inputs=bundle_inputs,
        raw_inputs=context.raw_inputs,
    )

    bundle_result = _pipeline_cli_bundle(bundle_context)
    if bundle_result.status != "ok":
        raise PipelineError("Bundle step failed; aborting release.")
    logs.extend(bundle_result.logs)
    receipts["bundle"] = bundle_result.data
    artifacts.update(bundle_result.artifacts)

    rules_inputs: Dict[str, object] = {}
    rules_version = context.get("rules-version") or context.get("version")
    if rules_version:
        rules_inputs["version"] = rules_version
    for key in ("rules-root", "manifest", "update-current", "keep-manifest"):
        value = context.inputs.get(key)
        if value is not None:
            rules_inputs[key] = value
    rules_context = PipelineContext(
        workspace_root=workspace_root,
        inputs=rules_inputs,
        raw_inputs={},
    )
    rules_result = _pipeline_rules_version(rules_context)
    if rules_result.status != "ok":
        raise PipelineError("Rule generation step failed; aborting release.")
    logs.extend(rules_result.logs)
    receipts["rules"] = rules_result.data
    if rules_result.artifacts.get("manifest"):
        artifacts["rules_manifest"] = rules_result.artifacts.get("manifest")

    skip_tests = _to_bool(context.get("skip-tests"))
    tests_receipt: Dict[str, object]
    if skip_tests:
        tests_receipt = {
            "status": "skipped",
            "reason": "skip-tests flag enabled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    else:
        tests_command = context.get_list("tests-command")
        if tests_command:
            command = [str(part) for part in tests_command]
        else:
            # Default to aware-tests runner (mirrors CI).
            command = [
                "uv",
                "run",
                "aware-tests",
                "--stable",
                "-v",
                "--fail-fast",
                "--no-warnings",
            ]
        try:
            result = _run_release_tests(
                command=command,
                cwd=workspace_root,
            )
            tests_receipt = {
                "status": "ok",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **result,
            }
            logs.append(result.get("stdout", ""))
        except PipelineError as exc:
            tests_receipt = {
                "status": "failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            }
            receipts["tests"] = tests_receipt
            raise
    receipts["tests"] = tests_receipt

    skip_workflow = _to_bool(context.get("skip-workflow"))
    workflow_receipt: Dict[str, object]
    if skip_workflow:
        workflow_receipt = {
            "status": "skipped",
            "reason": "skip-workflow flag enabled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    else:
        workflow_slug = context.get("workflow-slug") or "cli-release"
        workflow_ref = context.get("workflow-ref")
        workflow_inputs = _parse_key_value_pairs(context.get_list("workflow-input"))

        channel = context.get("channel")
        version = context.get("version")
        platform = context.get("platform") or "linux-x86_64"
        if channel:
            workflow_inputs.setdefault("channel", str(channel))
        if version:
            workflow_inputs.setdefault("version", str(version))
        if platform:
            workflow_inputs.setdefault("platform", str(platform))

        workflow_dry_run = _to_bool(context.get("workflow-dry-run"))
        token_env = context.get("workflow-token-env")

        spec = get_workflow(workflow_slug)
        try:
            dispatch_result = trigger_workflow(
                spec,
                ref=str(workflow_ref) if workflow_ref else None,
                inputs={key: str(value) for key, value in workflow_inputs.items()},
                token_env_override=str(token_env) if token_env else None,
                dry_run=workflow_dry_run,
            )
        except WorkflowTriggerError as exc:
            workflow_receipt = {
                "status": "failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            }
            receipts["workflow"] = workflow_receipt
            raise PipelineError(str(exc)) from exc

        workflow_receipt = {
            "status": "skipped" if dispatch_result.dry_run else "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": dispatch_result.model_dump(mode="json"),
        }
        if dispatch_result.response_headers:
            logs.append(str(dispatch_result.response_headers))
    receipts["workflow"] = workflow_receipt

    skip_publish = _to_bool(context.get("skip-publish"))
    if skip_publish:
        publish_receipt = {
            "status": "skipped",
            "reason": "skip-publish flag enabled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    else:
        dry_run_publish = _to_bool(context.get("dry-run"))
        try:
            publish_payload = publish_awarerelease_pypi(
                workspace_root=str(context.inputs.get("publish-workspace", workspace_root)),
                build_dir=str(context.get("publish-build-dir") or "dist"),
                pyproject_path=str(context.get("publish-pyproject") or "tools/release/pyproject.toml"),
                repository=str(context.get("publish-repository") or "pypi"),
                dry_run=dry_run_publish,
            )
        except Exception as exc:
            publish_receipt = {
                "status": "failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            }
            receipts["publish"] = publish_receipt
            raise PipelineError(f"Publish step failed: {exc}") from exc
        publish_receipt = {
            "status": "skipped" if dry_run_publish else "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": publish_payload,
        }
    receipts["publish"] = publish_receipt

    return PipelineResult(
        status="ok",
        artifacts=artifacts,
        receipts=receipts,
        logs=logs,
        data={
            "version": receipts["version"],
            "build": build_receipt,
            "bundle": bundle_result.data,
            "rules": rules_result.data,
            "tests": tests_receipt,
            "workflow": workflow_receipt,
            "publish": publish_receipt,
        },
    )


def _pipeline_tests_release(context: PipelineContext) -> PipelineResult:
    workspace_root = context.workspace_root
    bump_type = str(context.get("bump") or "patch")
    skip_versioning = _to_bool(context.get("skip-versioning"))
    dry_run = _to_bool(context.get("dry-run"))
    timestamp = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp_iso = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    project_dir = workspace_root / "tools" / "test-runner"
    version_config = VersionConfig.from_project(
        project_root=project_dir,
        module_relpath="aware_test_runner/__init__.py",
        changelog="CHANGELOG.md",
    )

    previous_version = read_version(version_config)
    new_version = previous_version
    changelog_entry = None

    if not skip_versioning:
        new_version = bump_version(previous_version, bump_type)
        if not dry_run:
            write_version(version_config, new_version)
            summary_lines = context.get_list("changelog-entry")
            changelog_entry = update_changelog(
                version_config,
                new_version,
                timestamp,
                [line for line in summary_lines if line],
            )

    logs: List[str] = []
    receipts: Dict[str, object] = {}
    artifacts: Dict[str, object] = {}

    built_wheels, build_receipt = _run_uv_build(
        workspace_root=workspace_root,
        project="tools/test-runner",
        out_dir="build/public/aware-test-runner/dist",
        extra_args=[],
    )
    artifacts["wheels"] = built_wheels
    receipts["build"] = build_receipt
    if build_receipt.get("stdout"):
        logs.append(build_receipt["stdout"])
    if build_receipt.get("stderr"):
        logs.append(build_receipt["stderr"])

    skip_tests = _to_bool(context.get("skip-tests"))
    if skip_tests:
        tests_receipt = {
            "status": "skipped",
            "reason": "skip-tests flag enabled",
            "timestamp": timestamp_iso,
        }
    else:
        env = os.environ.copy()
        env.setdefault(
            "AWARE_TEST_RUNNER_MANIFEST_DIRS",
            str(workspace_root / "configs" / "manifests"),
        )
        tests_command = [
            "uv",
            "run",
            "aware-tests",
            "--manifest",
            "oss",
            "--stable",
            "--no-warnings",
        ]
        tests_receipt = _run_release_tests(command=tests_command, cwd=workspace_root, env=env)
        logs.append(tests_receipt.get("stdout", ""))
        if tests_receipt.get("stderr"):
            logs.append(tests_receipt["stderr"])
    receipts["tests"] = tests_receipt

    skip_workflow = _to_bool(context.get("skip-workflow"))
    workflow_dry_run = _to_bool(context.get("workflow-dry-run"))
    workflow_receipt: Dict[str, object]
    if skip_workflow:
        workflow_receipt = {
            "status": "skipped",
            "reason": "skip-workflow flag enabled",
            "timestamp": timestamp_iso,
        }
    else:
        spec = get_workflow("tests-release")
        workflow_inputs = {
            "version": new_version,
            "dry_run": "true" if workflow_dry_run else "false",
            "timestamp": timestamp_iso,
        }
        try:
            dispatch_result = trigger_workflow(
                spec,
                inputs=workflow_inputs,
                dry_run=workflow_dry_run,
            )
        except WorkflowTriggerError as exc:
            workflow_receipt = {
                "status": "failed",
                "timestamp": timestamp_iso,
                "error": str(exc),
            }
            receipts["workflow"] = workflow_receipt
            raise PipelineError(str(exc)) from exc
        workflow_receipt = {
            "status": "skipped" if dispatch_result.dry_run else "ok",
            "timestamp": timestamp_iso,
            "payload": dispatch_result.model_dump(mode="json"),
        }
    receipts["workflow"] = workflow_receipt

    receipts["version"] = {
        "previous": previous_version,
        "new": new_version,
        "bump": bump_type,
        "timestamp": timestamp_iso,
        "changelog": str(version_config.changelog_path),
        "changelog_entry": changelog_entry,
        "skip_versioning": skip_versioning,
        "dry_run": dry_run,
    }
    artifacts["version"] = new_version

    return PipelineResult(
        status="ok",
        artifacts=artifacts,
        receipts=receipts,
        logs=[log for log in logs if log],
        data={
            "version": receipts["version"],
            "build": build_receipt,
            "tests": tests_receipt,
            "workflow": workflow_receipt,
        },
    )


def _pipeline_file_system_release(context: PipelineContext) -> PipelineResult:
    workspace_root = context.workspace_root
    bump_type = str(context.get("bump") or "patch")
    skip_versioning = _to_bool(context.get("skip-versioning"))
    dry_run = _to_bool(context.get("dry-run"))
    timestamp = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp_iso = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    project_dir = workspace_root / "libs" / "file_system"
    version_config = VersionConfig.from_project(
        project_root=project_dir,
        module_relpath="aware_file_system/__init__.py",
        changelog="CHANGELOG.md",
    )

    previous_version = read_version(version_config)
    new_version = previous_version
    changelog_entry = None

    if not skip_versioning:
        new_version = bump_version(previous_version, bump_type)
        if not dry_run:
            write_version(version_config, new_version)
            summary_lines = context.get_list("changelog-entry")
            changelog_entry = update_changelog(
                version_config,
                new_version,
                timestamp,
                [line for line in summary_lines if line],
            )

    logs: List[str] = []
    receipts: Dict[str, object] = {}
    artifacts: Dict[str, object] = {}

    built_wheels, build_receipt = _run_uv_build(
        workspace_root=workspace_root,
        project="libs/file_system",
        out_dir="build/public/aware-file-system/dist",
        extra_args=[],
    )
    artifacts["wheels"] = built_wheels
    receipts["build"] = build_receipt
    if build_receipt.get("stdout"):
        logs.append(build_receipt["stdout"])
    if build_receipt.get("stderr"):
        logs.append(build_receipt["stderr"])

    skip_tests = _to_bool(context.get("skip-tests"))
    if skip_tests:
        tests_receipt = {
            "status": "skipped",
            "reason": "skip-tests flag enabled",
            "timestamp": timestamp_iso,
        }
    else:
        tests_command = [
            "uv",
            "run",
            "--project",
            "libs/file_system",
            "pytest",
            "libs/file_system/tests",
        ]
        env = os.environ.copy()
        env.setdefault("UV_NO_WORKSPACE", "1")
        tests_receipt = _run_release_tests(command=tests_command, cwd=workspace_root, env=env)
        logs.append(tests_receipt.get("stdout", ""))
        if tests_receipt.get("stderr"):
            logs.append(tests_receipt["stderr"])
    receipts["tests"] = tests_receipt

    skip_workflow = _to_bool(context.get("skip-workflow"))
    workflow_dry_run = _to_bool(context.get("workflow-dry-run"))
    workflow_receipt: Dict[str, object]
    if skip_workflow:
        workflow_receipt = {
            "status": "skipped",
            "reason": "skip-workflow flag enabled",
            "timestamp": timestamp_iso,
        }
    else:
        spec = get_workflow("file-system-release")
        workflow_inputs = {
            "version": new_version,
            "dry_run": "true" if workflow_dry_run else "false",
            "timestamp": timestamp_iso,
        }
        try:
            dispatch_result = trigger_workflow(
                spec,
                inputs=workflow_inputs,
                dry_run=workflow_dry_run,
            )
        except WorkflowTriggerError as exc:
            workflow_receipt = {
                "status": "failed",
                "timestamp": timestamp_iso,
                "error": str(exc),
            }
            receipts["workflow"] = workflow_receipt
            raise PipelineError(str(exc)) from exc
        workflow_receipt = {
            "status": "skipped" if dispatch_result.dry_run else "ok",
            "timestamp": timestamp_iso,
            "payload": dispatch_result.model_dump(mode="json"),
        }
    receipts["workflow"] = workflow_receipt

    receipts["version"] = {
        "previous": previous_version,
        "new": new_version,
        "bump": bump_type,
        "timestamp": timestamp_iso,
        "changelog": str(project_dir / "CHANGELOG.md"),
        "changelog_entry": changelog_entry,
        "skip_versioning": skip_versioning,
        "dry_run": dry_run,
    }

    return PipelineResult(
        status="ok",
        artifacts=artifacts,
        receipts=receipts,
        logs=[log for log in logs if log],
        data={
            "version": receipts["version"],
            "build": build_receipt,
            "tests": tests_receipt,
            "workflow": workflow_receipt,
        },
    )


def _pipeline_environment_release(context: PipelineContext) -> PipelineResult:
    workspace_root = context.workspace_root
    bump_type = str(context.get("bump") or "patch")
    skip_versioning = _to_bool(context.get("skip-versioning"))
    dry_run = _to_bool(context.get("dry-run"))
    timestamp = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp_iso = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    project_dir = workspace_root / "libs" / "environment"
    version_config = VersionConfig.from_project(
        project_root=project_dir,
        module_relpath="aware_environment/__init__.py",
        changelog="CHANGELOG.md",
    )

    previous_version = read_version(version_config)
    new_version = previous_version
    changelog_entry = None

    if not skip_versioning:
        new_version = bump_version(previous_version, bump_type)
        if not dry_run:
            write_version(version_config, new_version)
            summary_lines = context.get_list("changelog-entry")
            changelog_entry = update_changelog(
                version_config,
                new_version,
                timestamp,
                [line for line in summary_lines if line],
            )

    logs: List[str] = []
    receipts: Dict[str, object] = {}
    artifacts: Dict[str, object] = {}

    built_wheels, build_receipt = _run_uv_build(
        workspace_root=workspace_root,
        project="libs/environment",
        out_dir="build/public/aware-environment/dist",
        extra_args=[],
    )
    artifacts["wheels"] = built_wheels
    receipts["build"] = build_receipt
    if build_receipt.get("stdout"):
        logs.append(build_receipt["stdout"])
    if build_receipt.get("stderr"):
        logs.append(build_receipt["stderr"])

    skip_tests = _to_bool(context.get("skip-tests"))
    if skip_tests:
        tests_receipt = {
            "status": "skipped",
            "reason": "skip-tests flag enabled",
            "timestamp": timestamp_iso,
        }
    else:
        tests_command = [
            "uv",
            "run",
            "--project",
            "libs/environment",
            "pytest",
            "libs/environment/tests",
        ]
        env = os.environ.copy()
        env.setdefault("UV_NO_WORKSPACE", "1")
        tests_receipt = _run_release_tests(command=tests_command, cwd=workspace_root, env=env)
        logs.append(tests_receipt.get("stdout", ""))
        if tests_receipt.get("stderr"):
            logs.append(tests_receipt["stderr"])
    receipts["tests"] = tests_receipt

    skip_workflow = _to_bool(context.get("skip-workflow"))
    workflow_dry_run = _to_bool(context.get("workflow-dry-run"))
    workflow_receipt: Dict[str, object]
    if skip_workflow:
        workflow_receipt = {
            "status": "skipped",
            "reason": "skip-workflow flag enabled",
            "timestamp": timestamp_iso,
        }
    else:
        spec = get_workflow("environment-release")
        workflow_inputs = {
            "version": new_version,
            "dry_run": "true" if workflow_dry_run else "false",
            "timestamp": timestamp_iso,
        }
        try:
            dispatch_result = trigger_workflow(
                spec,
                inputs=workflow_inputs,
                dry_run=workflow_dry_run,
            )
        except WorkflowTriggerError as exc:
            workflow_receipt = {
                "status": "failed",
                "timestamp": timestamp_iso,
                "error": str(exc),
            }
            receipts["workflow"] = workflow_receipt
            raise PipelineError(str(exc)) from exc
        workflow_receipt = {
            "status": "skipped" if dispatch_result.dry_run else "ok",
            "timestamp": timestamp_iso,
            "payload": dispatch_result.model_dump(mode="json"),
        }
    receipts["workflow"] = workflow_receipt

    receipts["version"] = {
        "previous": previous_version,
        "new": new_version,
        "bump": bump_type,
        "timestamp": timestamp_iso,
        "changelog": str(project_dir / "CHANGELOG.md"),
        "changelog_entry": changelog_entry,
        "skip_versioning": skip_versioning,
        "dry_run": dry_run,
    }

    return PipelineResult(
        status="ok",
        artifacts=artifacts,
        receipts=receipts,
        logs=[log for log in logs if log],
        data={
            "version": receipts["version"],
            "build": build_receipt,
            "tests": tests_receipt,
            "workflow": workflow_receipt,
        },
    )


def _pipeline_sdk_release(context: PipelineContext) -> PipelineResult:
    workspace_root = context.workspace_root
    bump_type = str(context.get("bump") or "patch")
    skip_versioning = _to_bool(context.get("skip-versioning"))
    dry_run = _to_bool(context.get("dry-run"))
    timestamp = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp_iso = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    project_dir = workspace_root / "apps" / "aware-sdk"
    version_config = VersionConfig.from_project(
        project_root=project_dir,
        module_relpath="aware_sdk/__init__.py",
        changelog="CHANGELOG.md",
    )

    previous_version = read_version(version_config)
    new_version = previous_version
    changelog_entry = None

    if not skip_versioning:
        new_version = bump_version(previous_version, bump_type)
        if not dry_run:
            write_version(version_config, new_version)
            summary_lines = context.get_list("changelog-entry")
            changelog_entry = update_changelog(
                version_config,
                new_version,
                timestamp,
                [line for line in summary_lines if line],
            )

    staging_root = _stage_sdk_sources(workspace_root)

    logs: List[str] = []
    receipts: Dict[str, object] = {}
    artifacts: Dict[str, object] = {}

    build_env = {"UV_NO_WORKSPACE": "1"}
    built_wheels, build_receipt = _run_uv_build(
        workspace_root=workspace_root,
        project=str(staging_root),
        out_dir="build/public/aware-sdk/dist",
        extra_args=[],
        env=build_env,
    )
    artifacts["wheels"] = built_wheels
    receipts["build"] = build_receipt
    if build_receipt.get("stdout"):
        logs.append(build_receipt["stdout"])
    if build_receipt.get("stderr"):
        logs.append(build_receipt["stderr"])

    skip_tests = _to_bool(context.get("skip-tests"))
    if skip_tests:
        tests_receipt = {
            "status": "skipped",
            "reason": "skip-tests flag enabled",
            "timestamp": timestamp_iso,
        }
    else:
        env = os.environ.copy()
        env.setdefault("UV_NO_WORKSPACE", "1")
        env["AWARE_ROOT"] = str(staging_root)
        manifest_dirs = str(staging_root / "aware_sdk" / "configs" / "manifests")
        existing_manifest_dirs = env.get("AWARE_TEST_RUNNER_MANIFEST_DIRS")
        env["AWARE_TEST_RUNNER_MANIFEST_DIRS"] = (
            manifest_dirs if not existing_manifest_dirs else os.pathsep.join([manifest_dirs, existing_manifest_dirs])
        )
        env["AWARE_TERMINAL_DEV_ROOT"] = str(staging_root)
        env["AWARE_TERMINAL_MANIFEST_ROOT"] = str(
            staging_root / "libs" / "providers" / "terminal" / "aware_terminal_providers" / "providers"
        )
        stub_script = staging_root / "tools" / "terminal" / "_ci_update_provider_versions.py"
        stub_script.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "from __future__ import annotations",
                    "import json",
                    "import os",
                    "from datetime import datetime, timezone",
                    "from pathlib import Path",
                    "import sys",
                    "",
                    "def _provider_root() -> Path:",
                    "    env_override = os.environ.get('AWARE_TERMINAL_MANIFEST_ROOT')",
                    "    if env_override:",
                    "        return Path(env_override).expanduser().resolve()",
                    "    if len(sys.argv) > 1:",
                    "        return Path(sys.argv[1]).expanduser().resolve()",
                    "    return Path(__file__).resolve().parents[2] / 'libs' / 'providers' / 'terminal' / 'aware_terminal_providers' / 'providers'",
                    "",
                    "def main() -> int:",
                    "    root = _provider_root()",
                    "    if not root.exists():",
                    "        return 0",
                    "    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')",
                    "    for manifest_path in root.glob('*/releases.json'):",
                    "        try:",
                    "            data = json.loads(manifest_path.read_text(encoding='utf-8'))",
                    "        except Exception:",
                    "            data = {'provider': manifest_path.parent.name, 'channels': {}}",
                    "        channels = data.setdefault('channels', {})",
                    "        if not isinstance(channels, dict):",
                    "            channels = {}",
                    "            data['channels'] = channels",
                    "        if not channels:",
                    "            channels['latest'] = {}",
                    "        for channel in channels.values():",
                    "            if isinstance(channel, dict):",
                    "                channel['updated_at'] = timestamp",
                    "        manifest_path.parent.mkdir(parents=True, exist_ok=True)",
                    "        manifest_path.write_text(json.dumps(data, indent=2) + '\\n', encoding='utf-8')",
                    "    return 0",
                    "",
                    "if __name__ == '__main__':",
                    "    raise SystemExit(main())",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        stub_script.chmod(0o755)
        env["AWARE_TERMINAL_MANIFEST_UPDATE_SCRIPT"] = str(
            staging_root / "tools" / "terminal" / "_ci_update_provider_versions.py"
        )
        env["AWARE_TERMINAL_ALLOW_MANIFEST_REFRESH"] = "1"
        existing_pytest_opts = env.get("PYTEST_ADDOPTS")
        filter_expr = "-k 'not publish_pypi'"
        env["PYTEST_ADDOPTS"] = filter_expr if not existing_pytest_opts else f"{existing_pytest_opts} {filter_expr}"
        tests_command = [
            "uv",
            "run",
            "--project",
            str(staging_root / "tools" / "test-runner"),
            "--with",
            str(staging_root / "tools" / "release"),
            "--with",
            str(staging_root / "tools" / "release-pipeline"),
            "--with",
            f"{staging_root / 'libs' / 'file_system'}[test]",
            "--with",
            str(staging_root / "libs" / "environment"),
            "--with",
            f"{staging_root / 'tools' / 'terminal'}[test]",
            "--with",
            f"{staging_root / 'libs' / 'providers' / 'terminal'}[test]",
            "aware-tests",
            "--manifest",
            "oss",
            "--stable",
            "--no-warnings",
        ]
        tests_receipt = _run_release_tests(command=tests_command, cwd=staging_root, env=env)
        logs.append(tests_receipt.get("stdout", ""))
        if tests_receipt.get("stderr"):
            logs.append(tests_receipt["stderr"])
    receipts["tests"] = tests_receipt

    skip_workflow = _to_bool(context.get("skip-workflow"))
    workflow_dry_run = _to_bool(context.get("workflow-dry-run"))
    workflow_receipt: Dict[str, object]
    if skip_workflow:
        workflow_receipt = {
            "status": "skipped",
            "reason": "skip-workflow flag enabled",
            "timestamp": timestamp_iso,
        }
    else:
        spec = get_workflow("sdk-release")
        workflow_inputs = {
            "version": new_version,
            "dry_run": "true" if workflow_dry_run else "false",
            "timestamp": timestamp_iso,
        }
        try:
            dispatch_result = trigger_workflow(
                spec,
                inputs=workflow_inputs,
                dry_run=workflow_dry_run,
            )
        except WorkflowTriggerError as exc:
            workflow_receipt = {
                "status": "failed",
                "timestamp": timestamp_iso,
                "error": str(exc),
            }
            receipts["workflow"] = workflow_receipt
            raise PipelineError(str(exc)) from exc
        workflow_receipt = {
            "status": "skipped" if dispatch_result.dry_run else "ok",
            "timestamp": timestamp_iso,
            "payload": dispatch_result.model_dump(mode="json"),
        }
    receipts["workflow"] = workflow_receipt

    receipts["version"] = {
        "previous": previous_version,
        "new": new_version,
        "bump": bump_type,
        "timestamp": timestamp_iso,
        "changelog": str(project_dir / "CHANGELOG.md"),
        "changelog_entry": changelog_entry,
        "skip_versioning": skip_versioning,
        "dry_run": dry_run,
    }

    return PipelineResult(
        status="ok",
        artifacts=artifacts,
        receipts=receipts,
        logs=[log for log in logs if log],
        data={
            "version": receipts["version"],
            "build": build_receipt,
            "tests": tests_receipt,
            "workflow": workflow_receipt,
        },
    )


def _pipeline_terminal_release(context: PipelineContext) -> PipelineResult:
    workspace_root = context.workspace_root
    timestamp_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    packages = [
        {
            "name": "aware-terminal",
            "project": workspace_root / "tools" / "terminal",
            "out_dir": workspace_root / "build" / "public" / "aware-terminal" / "dist",
            "test_command": [
                "uv",
                "run",
                "--project",
                "tools/terminal",
                "pytest",
                "-q",
            ],
        },
        {
            "name": "aware-terminal-providers",
            "project": workspace_root / "libs" / "providers" / "terminal",
            "out_dir": workspace_root / "build" / "public" / "aware-terminal-providers" / "dist",
            "test_command": [
                "uv",
                "run",
                "--project",
                "libs/providers/terminal",
                "pytest",
                "-q",
            ],
        },
    ]

    if _to_bool(context.get("include-control-center")):
        packages.append(
            {
                "name": "aware-terminal-control-center",
                "project": workspace_root / "tools" / "terminal-control-center",
                "out_dir": workspace_root / "build" / "public" / "aware-terminal-control-center" / "dist",
                "test_command": [
                    "uv",
                    "run",
                    "--project",
                    "tools/terminal-control-center",
                    "pytest",
                    "-q",
                ],
            }
        )

    artifacts: Dict[str, object] = {"wheels": {}}
    receipts: Dict[str, object] = {}
    logs: List[str] = []

    skip_tests = _to_bool(context.get("skip-tests"))

    for pkg in packages:
        project_rel = pkg["project"].relative_to(workspace_root)
        out_rel = pkg["out_dir"].relative_to(workspace_root)
        built_wheels, build_receipt = _run_uv_build(
            workspace_root=workspace_root,
            project=str(project_rel),
            out_dir=str(out_rel),
            extra_args=[],
        )
        artifacts["wheels"][pkg["name"]] = built_wheels
        receipts[pkg["name"]] = {"build": build_receipt}
        if build_receipt.get("stdout"):
            logs.append(build_receipt["stdout"])
        if build_receipt.get("stderr"):
            logs.append(build_receipt["stderr"])

        if skip_tests:
            receipts[pkg["name"]]["tests"] = {
                "status": "skipped",
                "reason": "skip-tests flag enabled",
                "timestamp": timestamp_iso,
            }
            continue

        test_receipt = _run_release_tests(
            command=pkg["test_command"],
            cwd=pkg["project"],
        )
        receipts[pkg["name"]]["tests"] = test_receipt
        if test_receipt.get("stdout"):
            logs.append(test_receipt["stdout"])
        if test_receipt.get("stderr"):
            logs.append(test_receipt["stderr"])

    return PipelineResult(
        status="ok",
        artifacts=artifacts,
        receipts=receipts,
        logs=[log for log in logs if log],
    )


def _register_builtin_pipelines() -> None:
    register_pipeline(
        PipelineSpec(
            slug="tests-release",
            description="Build, test, and publish aware-test-runner package.",
            runner=_pipeline_tests_release,
            inputs={
                "bump": PipelineInputSpec(description="Version bump type (patch/minor/major)", default="patch"),
                "skip-versioning": PipelineInputSpec(
                    description="Skip version/changelog updates (true/false)", default="false"
                ),
                "changelog-entry": PipelineInputSpec(description="Additional changelog bullet", multiple=True),
                "skip-tests": PipelineInputSpec(description="Skip tests execution (true/false)", default="false"),
                "skip-workflow": PipelineInputSpec(description="Skip publish workflow (true/false)", default="false"),
                "workflow-dry-run": PipelineInputSpec(
                    description="Publish workflow dry-run (true/false)", default="true"
                ),
                "dry-run": PipelineInputSpec(description="Pipeline dry-run (true/false)", default="false"),
            },
            artifacts=["wheels", "version"],
            receipts=["version", "build", "tests", "workflow"],
        )
    )

    register_pipeline(
        PipelineSpec(
            slug="file-system-release",
            description="Build, test, and publish aware-file-system package.",
            runner=_pipeline_file_system_release,
            inputs={
                "bump": PipelineInputSpec(description="Version bump type (patch/minor/major)", default="patch"),
                "skip-versioning": PipelineInputSpec(
                    description="Skip version/changelog updates (true/false)", default="false"
                ),
                "changelog-entry": PipelineInputSpec(description="Additional changelog bullet", multiple=True),
                "skip-tests": PipelineInputSpec(description="Skip tests execution (true/false)", default="false"),
                "skip-workflow": PipelineInputSpec(description="Skip publish workflow (true/false)", default="false"),
                "workflow-dry-run": PipelineInputSpec(
                    description="Publish workflow dry-run (true/false)", default="true"
                ),
                "dry-run": PipelineInputSpec(description="Pipeline dry-run (true/false)", default="false"),
            },
            artifacts=["wheels"],
            receipts=["version", "build", "tests", "workflow"],
        )
    )

    register_pipeline(
        PipelineSpec(
            slug="environment-release",
            description="Build, test, and publish aware-environment package.",
            runner=_pipeline_environment_release,
            inputs={
                "bump": PipelineInputSpec(description="Version bump type (patch/minor/major)", default="patch"),
                "skip-versioning": PipelineInputSpec(
                    description="Skip version/changelog updates (true/false)", default="false"
                ),
                "changelog-entry": PipelineInputSpec(description="Additional changelog bullet", multiple=True),
                "skip-tests": PipelineInputSpec(description="Skip tests execution (true/false)", default="false"),
                "skip-workflow": PipelineInputSpec(description="Skip publish workflow (true/false)", default="false"),
                "workflow-dry-run": PipelineInputSpec(
                    description="Publish workflow dry-run (true/false)", default="true"
                ),
                "dry-run": PipelineInputSpec(description="Pipeline dry-run (true/false)", default="false"),
            },
            artifacts=["wheels"],
            receipts=["version", "build", "tests", "workflow"],
        )
    )

    register_pipeline(
        PipelineSpec(
            slug="sdk-release",
            description="Build, test, and publish aware-sdk bundle.",
            runner=_pipeline_sdk_release,
            inputs={
                "bump": PipelineInputSpec(description="Version bump type (patch/minor/major)", default="patch"),
                "skip-versioning": PipelineInputSpec(
                    description="Skip version/changelog updates (true/false)", default="false"
                ),
                "changelog-entry": PipelineInputSpec(description="Additional changelog bullet", multiple=True),
                "skip-tests": PipelineInputSpec(description="Skip tests execution (true/false)", default="false"),
                "skip-workflow": PipelineInputSpec(description="Skip publish workflow (true/false)", default="false"),
                "workflow-dry-run": PipelineInputSpec(
                    description="Publish workflow dry-run (true/false)", default="true"
                ),
                "dry-run": PipelineInputSpec(description="Pipeline dry-run (true/false)", default="false"),
            },
            artifacts=["wheels"],
            receipts=["version", "build", "tests", "workflow"],
        )
    )

    register_pipeline(
        PipelineSpec(
            slug="terminal-release",
            description="Build and test aware-terminal packages.",
            runner=_pipeline_terminal_release,
            inputs={
                "skip-tests": PipelineInputSpec(description="Skip tests execution (true/false)", default="false"),
                "include-control-center": PipelineInputSpec(
                    description="Also build/test aware-terminal-control-center", default="false"
                ),
            },
            artifacts=["wheels"],
            receipts=["aware-terminal", "aware-terminal-providers", "aware-terminal-control-center"],
        )
    )

    register_pipeline(
        PipelineSpec(
            slug="cli-bundle",
            description="Bundle aware-cli artefacts (wheels, providers, manifest, optional lockfile).",
            runner=_pipeline_cli_bundle,
            inputs={
                "channel": PipelineInputSpec(description="Release channel", required=True),
                "version": PipelineInputSpec(description="Bundle version", required=True),
                "platform": PipelineInputSpec(description="Target platform", default="linux-x86_64"),
                "wheel": PipelineInputSpec(description="Wheel path", required=True, multiple=True),
                "output-dir": PipelineInputSpec(description="Output directory", default="releases"),
                "providers-dir": PipelineInputSpec(description="Additional provider directories", multiple=True),
                "provider-wheel": PipelineInputSpec(description="Additional provider wheels", multiple=True),
                "dependencies-file": PipelineInputSpec(description="Additional requirements file"),
                "manifest-override": PipelineInputSpec(description="Manifest overrides (key=value)", multiple=True),
                "generate-lock": PipelineInputSpec(description="Generate lockfile (true/false)", default="false"),
                "lock-output": PipelineInputSpec(description="Lockfile output path"),
                "python-version": PipelineInputSpec(description="Python version for lock generation"),
            },
            artifacts=["archive", "manifest", "lock"],
        )
    )

    register_pipeline(
        PipelineSpec(
            slug="cli-rules",
            description="Regenerate aware-cli rule versions and manifest.",
            runner=_pipeline_rules_version,
            inputs={
                "version": PipelineInputSpec(description="Optional CLI version override"),
                "rules-root": PipelineInputSpec(description="Rules root directory", default="docs/rules"),
                "manifest": PipelineInputSpec(description="Manifest output path", default="build/rule-manifest.json"),
                "update-current": PipelineInputSpec(description="Update strategy for rules/current", default="copy"),
                "keep-manifest": PipelineInputSpec(
                    description="Append to existing manifest (true/false)", default="false"
                ),
            },
            artifacts=["manifest"],
        )
    )

    register_pipeline(
        PipelineSpec(
            slug="terminal-providers",
            description="Refresh and validate terminal provider manifests.",
            runner=_pipeline_terminal_providers,
            inputs={
                "manifests-dir": PipelineInputSpec(
                    description="Root directory containing provider manifests",
                    default="libs/providers/terminal/aware_terminal_providers/providers",
                ),
                "skip-refresh": PipelineInputSpec(
                    description="Skip provider refresh step (true/false)", default="false"
                ),
            },
            artifacts=["manifests"],
        )
    )

    register_pipeline(
        PipelineSpec(
            slug="cli-release-e2e",
            description="Execute full aware-release flow (bundle, rules, tests, workflow, publish).",
            runner=_pipeline_cli_release_e2e,
            inputs={
                "channel": PipelineInputSpec(description="Release channel", required=True),
                "version": PipelineInputSpec(description="Release version", required=True),
                "platform": PipelineInputSpec(description="Target platform", default="linux-x86_64"),
                "wheel": PipelineInputSpec(description="Additional wheel path", multiple=True),
                "bump": PipelineInputSpec(description="Version bump type (patch/minor/major)", default="patch"),
                "skip-versioning": PipelineInputSpec(description="Skip version update (true/false)", default="false"),
                "changelog-entry": PipelineInputSpec(description="Changelog bullet entry", multiple=True),
                "skip-build": PipelineInputSpec(
                    description="Skip building aware-cli wheel (true/false)", default="false"
                ),
                "build-project": PipelineInputSpec(description="Project path for uv build", default="tools/cli"),
                "build-out-dir": PipelineInputSpec(description="Output directory for built wheels", default="dist"),
                "build-arg": PipelineInputSpec(description="Extra arguments for uv build", multiple=True),
                "rules-root": PipelineInputSpec(description="Rules root directory"),
                "manifest": PipelineInputSpec(description="Rules manifest output path"),
                "update-current": PipelineInputSpec(description="Update rules/current strategy"),
                "keep-manifest": PipelineInputSpec(
                    description="Append to existing manifest (true/false)", default="false"
                ),
                "skip-tests": PipelineInputSpec(description="Skip Aware test suite (true/false)", default="false"),
                "tests-command": PipelineInputSpec(description="Override test command (list entries)", multiple=True),
                "skip-workflow": PipelineInputSpec(description="Skip workflow dispatch (true/false)", default="false"),
                "workflow-slug": PipelineInputSpec(description="Workflow slug", default="cli-release"),
                "workflow-ref": PipelineInputSpec(description="Workflow ref override"),
                "workflow-input": PipelineInputSpec(description="Extra workflow inputs key=value", multiple=True),
                "workflow-token-env": PipelineInputSpec(description="Workflow token env override"),
                "workflow-dry-run": PipelineInputSpec(description="Workflow dry-run (true/false)", default="false"),
                "skip-publish": PipelineInputSpec(description="Skip PyPI publish (true/false)", default="false"),
                "dry-run": PipelineInputSpec(description="Global dry-run (true/false)", default="false"),
                "publish-workspace": PipelineInputSpec(description="Workspace root override for publish"),
                "publish-build-dir": PipelineInputSpec(description="Build directory for publish", default="dist"),
                "publish-pyproject": PipelineInputSpec(
                    description="aware-release pyproject path", default="tools/release/pyproject.toml"
                ),
                "publish-repository": PipelineInputSpec(description="PyPI repository", default="pypi"),
            },
            artifacts=["archive", "manifest", "rules_manifest", "wheels"],
            receipts=["version", "build", "bundle", "rules", "tests", "workflow", "publish"],
        )
    )


_register_builtin_pipelines()


__all__ = [
    "PipelineContext",
    "PipelineError",
    "PipelineInputSpec",
    "PipelineResult",
    "PipelineSpec",
    "get_pipeline",
    "list_pipelines",
    "register_pipeline",
]
