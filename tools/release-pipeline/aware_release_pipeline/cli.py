from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from aware_release.workflows import WorkflowTriggerError, trigger_workflow
from aware_release.secrets import use_dotenv

from .pipeline import (
    prepare_release,
    publish_release,
    publish_awarerelease_pypi,
    refresh_terminal_providers,
    render_rules,
    validate_terminal_providers,
)
from .pipelines import (
    PipelineContext,
    PipelineError,
    PipelineResult,
    PipelineSpec,
    get_pipeline as get_pipeline_spec,
    list_pipelines as list_pipeline_specs,
)
from .workflows import get_workflow, list_workflows


def _load_local_env() -> None:
    """Best-effort load of repo-local .env for convenience."""

    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency declared, but guard just in case
        return

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    use_dotenv(repo_root / ".env")
    env_file = repo_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)


def _add_prepare_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--channel", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--platform", default="linux-x86_64")
    parser.add_argument("--wheel", action="append", required=True)
    parser.add_argument("--output-dir", default="releases")
    parser.add_argument("--providers-dir", action="append")
    parser.add_argument("--provider-wheel", action="append")
    parser.add_argument("--dependencies-file")
    parser.add_argument("--manifest-override", action="append")
    parser.add_argument("--generate-lock", action="store_true")
    parser.add_argument("--lock-output")
    parser.add_argument("--python-version")
    parser.add_argument("--workspace-root", default=".")


def _add_publish_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--channel", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--platform", default="linux-x86_64")
    parser.add_argument("--output-dir", default="releases")
    parser.add_argument("--adapter", default="noop")
    parser.add_argument("--adapter-command")
    parser.add_argument("--adapter-arg", action="append")
    parser.add_argument("--releases-json")
    parser.add_argument("--url")
    parser.add_argument("--notes")
    parser.add_argument("--signature-command")
    parser.add_argument("--actor")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--workspace-root", default=".")


def main(argv: list[str] | None = None) -> int:
    _load_local_env()
    parser = argparse.ArgumentParser(prog="release-pipeline", description="aware_release orchestration helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    cli_parser = subparsers.add_parser("cli", help="aware-cli bundle workflows")
    cli_subparsers = cli_parser.add_subparsers(dest="cli_command", required=True)

    prepare = cli_subparsers.add_parser("prepare", help="Bundle wheels, validate manifest, generate lockfiles")
    _add_prepare_arguments(prepare)

    publish = cli_subparsers.add_parser("publish", help="Publish bundle using configured adapter")
    _add_publish_arguments(publish)

    # Legacy aliases (to be deprecated once all callers migrate)
    legacy_prepare = subparsers.add_parser("prepare", help=argparse.SUPPRESS)
    _add_prepare_arguments(legacy_prepare)
    legacy_publish = subparsers.add_parser("publish", help=argparse.SUPPRESS)
    _add_publish_arguments(legacy_publish)

    rules = subparsers.add_parser("rules", help="Rule automation helpers")
    rules_subparsers = rules.add_subparsers(dest="rules_command", required=True)

    rules_render = rules_subparsers.add_parser("render", help="Generate rule versions via aware-cli")
    rules_render.add_argument("--version")
    rules_render.add_argument("--rules-root", default="docs/rules")
    rules_render.add_argument("--manifest", default="build/rule-manifest.json")
    rules_render.add_argument("--update-current", choices=["copy", "symlink"], default="copy")
    rules_render.add_argument("--workspace-root", default=".")
    rules_render.add_argument("--keep-manifest", action="store_true", help="Append to existing manifest instead of recreating")

    terminal = subparsers.add_parser("terminal", help="Terminal providers automation")
    terminal_subparsers = terminal.add_subparsers(dest="terminal_command", required=True)

    terminal_refresh = terminal_subparsers.add_parser("refresh", help="Refresh provider manifests via updater script")
    terminal_refresh.add_argument("--workspace-root", default=".")
    terminal_refresh.add_argument("--manifests-dir", default="libs/providers/terminal/aware_terminal_providers/providers")

    terminal_validate = terminal_subparsers.add_parser("validate", help="Validate provider manifests for schema and duplicates")
    terminal_validate.add_argument("--workspace-root", default=".")
    terminal_validate.add_argument("--manifests-dir", default="libs/providers/terminal/aware_terminal_providers/providers")

    aware_release_cmd = cli_subparsers.add_parser("aware-release", help="aware-release package helpers")
    aware_release_subparsers = aware_release_cmd.add_subparsers(dest="aware_release_command", required=True)
    aware_release_publish = aware_release_subparsers.add_parser("publish-pypi", help="Build and publish aware-release to PyPI")
    aware_release_publish.add_argument("--workspace-root", default=".")
    aware_release_publish.add_argument("--build-dir", default="dist")
    aware_release_publish.add_argument("--pyproject", default="tools/release/pyproject.toml")
    aware_release_publish.add_argument("--repository", default="pypi")
    aware_release_publish.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)

    workflow = subparsers.add_parser("workflow", help="Inspect and trigger registered workflows")
    workflow_subparsers = workflow.add_subparsers(dest="workflow_command", required=True)

    workflow_list = workflow_subparsers.add_parser("list", help="List known workflows")

    workflow_trigger = workflow_subparsers.add_parser("trigger", help="Dispatch a workflow by slug")
    workflow_trigger.add_argument("--workflow", required=True, dest="workflow_slug")
    workflow_trigger.add_argument("--ref")
    workflow_trigger.add_argument("--input", action="append")
    workflow_trigger.add_argument("--token-env")
    workflow_trigger.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    workflow_trigger.add_argument("--github-api", default="https://api.github.com")

    sdk_parser = subparsers.add_parser("sdk", help="aware-sdk helper commands")
    sdk_subparsers = sdk_parser.add_subparsers(dest="sdk_command", required=True)
    sdk_sync = sdk_subparsers.add_parser("sync", help="Sync staged SDK export into a target repository")
    sdk_sync.add_argument("--export-root", default="build/sdk-export")
    sdk_sync.add_argument("--target", required=True)
    sdk_sync.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)

    sdk_publish = sdk_subparsers.add_parser("publish", help="Run the sdk-release pipeline, sync the export, commit, and push")
    sdk_publish.add_argument("--target", required=True)
    sdk_publish.add_argument("--branch", required=True)
    sdk_publish.add_argument("--workspace-root", default=".")
    sdk_publish.add_argument("--skip-versioning", action=argparse.BooleanOptionalAction, default=True)
    sdk_publish.add_argument("--skip-workflow", action=argparse.BooleanOptionalAction, default=True)
    sdk_publish.add_argument("--pipeline-dry-run", action=argparse.BooleanOptionalAction, default=False)
    sdk_publish.add_argument("--skip-push", action=argparse.BooleanOptionalAction, default=False)
    sdk_publish.add_argument("--commit-message")

    pipeline_cmd = subparsers.add_parser("pipeline", help="Composite pipeline registry commands")
    pipeline_subparsers = pipeline_cmd.add_subparsers(dest="pipeline_command", required=True)

    pipeline_list = pipeline_subparsers.add_parser("list", help="List registered pipelines")

    pipeline_run = pipeline_subparsers.add_parser("run", help="Execute a registered pipeline")
    pipeline_run.add_argument("--pipeline", required=True, dest="pipeline_slug")
    pipeline_run.add_argument("--input", action="append")
    pipeline_run.add_argument("--workspace-root", default=".")

    args = parser.parse_args(argv)

    if args.command == "cli":
        if args.cli_command == "prepare":
            return _run_prepare(args)
        if args.cli_command == "publish":
            return _run_publish(args)
        if args.cli_command == "aware-release" and args.aware_release_command == "publish-pypi":
            payload = publish_awarerelease_pypi(
                workspace_root=args.workspace_root,
                build_dir=args.build_dir,
                pyproject_path=args.pyproject,
                repository=args.repository,
                dry_run=args.dry_run,
            )
            print(json.dumps(payload, indent=2))
            return 0

    if args.command == "sdk":
        if args.sdk_command == "sync":
            payload = _sync_sdk_export(
                export_root=args.export_root,
                target_root=args.target,
                dry_run=args.dry_run,
            )
            print(json.dumps(payload, indent=2))
            return 0

        if args.sdk_command == "publish":
            payload = _publish_sdk_export(
                workspace_root=args.workspace_root,
                target_root=args.target,
                branch=args.branch,
                skip_versioning=args.skip_versioning,
                skip_workflow=args.skip_workflow,
                pipeline_dry_run=args.pipeline_dry_run,
                skip_push=args.skip_push,
                commit_message=args.commit_message,
            )
            print(json.dumps(payload, indent=2))
            return 0

    if args.command == "prepare":  # legacy path
        return _run_prepare(args)

    if args.command == "publish":  # legacy path
        return _run_publish(args)

    if args.command == "rules":
        if args.rules_command == "render":
            payload = render_rules(
                version=args.version,
                rules_root=args.rules_root,
                manifest_path=args.manifest,
                update_current=args.update_current,
                workspace_root=args.workspace_root,
                clean_manifest=not args.keep_manifest,
            )
            print(json.dumps(payload.to_dict(), indent=2))
            return 0

    if args.command == "terminal":
        if args.terminal_command == "refresh":
            payload = refresh_terminal_providers(
                workspace_root=args.workspace_root,
                manifests_dir=args.manifests_dir,
            )
            print(json.dumps(payload.to_dict(), indent=2))
            return 0
        if args.terminal_command == "validate":
            payload = validate_terminal_providers(
                workspace_root=args.workspace_root,
                manifests_dir=args.manifests_dir,
            )
            print(json.dumps(payload.to_dict(), indent=2))
            if payload.issues:
                return 1
            return 0

    if args.command == "workflow":
        if args.workflow_command == "list":
            specs = [spec.model_dump(mode="json") for spec in list_workflows()]
            print(json.dumps(specs, indent=2))
            return 0

        if args.workflow_command == "trigger":
            try:
                spec = get_workflow(args.workflow_slug)
            except KeyError as exc:
                print(str(exc), file=sys.stderr)
                return 2

            input_values = _parse_key_value_args(args.input or [])
            try:
                result = trigger_workflow(
                    spec,
                    ref=args.ref,
                    inputs=input_values,
                    token_env_override=args.token_env,
                    dry_run=args.dry_run,
                    github_api=args.github_api,
                )
            except WorkflowTriggerError as exc:
                print(str(exc), file=sys.stderr)
                return 2

            print(json.dumps(result.model_dump(mode="json"), indent=2))
            return 0

    if args.command == "pipeline":
        if args.pipeline_command == "list":
            specs = [spec.to_dict() for spec in list_pipeline_specs()]
            print(json.dumps(specs, indent=2))
            return 0

        if args.pipeline_command == "run":
            try:
                spec = get_pipeline_spec(args.pipeline_slug)
            except KeyError as exc:
                print(str(exc), file=sys.stderr)
                return 2

            try:
                provided_inputs = _parse_pipeline_inputs(args.input or [])
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2

            try:
                resolved_inputs = _resolve_pipeline_inputs(spec, provided_inputs)
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2

            context = PipelineContext(
                workspace_root=Path(args.workspace_root).resolve(),
                inputs=resolved_inputs,
                raw_inputs=provided_inputs,
            )

            try:
                result = spec.runner(context)
            except PipelineError as exc:
                print(str(exc), file=sys.stderr)
                return 2

            payload = {
                "pipeline": spec.slug,
                "status": result.status,
                "artifacts": result.artifacts,
                "receipts": result.receipts,
                "logs": result.logs,
                "next_steps": result.next_steps,
                "data": result.data,
            }
            print(json.dumps(payload, indent=2))
            return 0

    parser.error("Unknown command")
    return 1


def _run_prepare(args: argparse.Namespace) -> int:
    payload = prepare_release(
        channel=args.channel,
        version=args.version,
        platform=args.platform,
        wheels=args.wheel,
        output_dir=args.output_dir,
        providers_dir=args.providers_dir,
        provider_wheels=args.provider_wheel,
        dependencies_file=args.dependencies_file,
        manifest_overrides=args.manifest_override,
        generate_lockfile=args.generate_lock,
        lock_output=args.lock_output,
        python_version=args.python_version,
        workspace_root=args.workspace_root,
    )
    print(json.dumps(payload.to_dict(), indent=2))
    return 0


def _run_publish(args: argparse.Namespace) -> int:
    adapter_options = _parse_key_value_args(args.adapter_arg or [])
    if args.adapter_command:
        adapter_options["command"] = args.adapter_command
    payload = publish_release(
        channel=args.channel,
        version=args.version,
        platform=args.platform,
        output_dir=args.output_dir,
        adapter=args.adapter,
        adapter_options=adapter_options,
        releases_index=args.releases_json,
        url=args.url,
        notes=args.notes,
        dry_run=args.dry_run,
        signature_command=args.signature_command,
        actor=args.actor,
        workspace_root=args.workspace_root,
    )
    print(json.dumps(payload.to_dict(), indent=2))
    return 0


def _sync_sdk_export(*, export_root: str, target_root: str, dry_run: bool) -> Dict[str, object]:
    export_path = Path(export_root).resolve()
    target_path = Path(target_root).resolve()

    if not export_path.is_dir():
        raise FileNotFoundError(f"Export root not found: {export_path}")
    if not target_path.exists():
        raise FileNotFoundError(f"Target path not found: {target_path}")
    if not target_path.is_dir():
        raise NotADirectoryError(f"Target path is not a directory: {target_path}")

    git_dir = target_path / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        raise RuntimeError(f"Target path does not appear to be a git repository (missing {git_dir})")

    if dry_run:
        export_entries = sorted(str(path.relative_to(export_path)) for path in export_path.rglob("*"))
        target_entries = sorted(
            str(path.relative_to(target_path))
            for path in target_path.rglob("*")
            if ".git" not in path.parts
        )
        planned_removals = [
            entry for entry in target_entries if not (export_path / entry).exists()
        ]
        planned_additions = [
            entry for entry in export_entries if not (target_path / entry).exists()
        ]
        return {
            "status": "dry_run",
            "export_root": str(export_path),
            "target_root": str(target_path),
            "planned_removals": planned_removals,
            "planned_additions": planned_additions,
        }

    for entry in list(target_path.iterdir()):
        if entry.name == ".git":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()

    for item in export_path.iterdir():
        destination = target_path / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)

    return {
        "status": "synced",
        "export_root": str(export_path),
        "target_root": str(target_path),
    }


def _run_sdk_pipeline(
    *,
    workspace_root: Path,
    skip_versioning: bool,
    skip_workflow: bool,
    dry_run: bool,
) -> PipelineResult:
    spec = get_pipeline_spec("sdk-release")
    context = PipelineContext(
        workspace_root=workspace_root,
        inputs={
            "skip-versioning": skip_versioning,
            "skip-workflow": skip_workflow,
            "dry-run": dry_run,
        },
        raw_inputs={},
    )
    return spec.runner(context)


def _run_git_command(args: List[str], *, cwd: Path, capture_output: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(cwd),
        check=True,
        text=True,
        capture_output=capture_output,
    )


def _publish_sdk_export(
    *,
    workspace_root: str,
    target_root: str,
    branch: str,
    skip_versioning: bool,
    skip_workflow: bool,
    pipeline_dry_run: bool,
    skip_push: bool,
    commit_message: str | None,
) -> Dict[str, object]:
    workspace = Path(workspace_root).resolve()
    target = Path(target_root).resolve()

    pipeline_result = _run_sdk_pipeline(
        workspace_root=workspace,
        skip_versioning=skip_versioning,
        skip_workflow=skip_workflow,
        dry_run=pipeline_dry_run,
    )
    if pipeline_result.status != "ok":
        raise PipelineError("sdk-release pipeline did not complete successfully")

    export_root = workspace / "build" / "sdk-export"
    sync_payload = _sync_sdk_export(
        export_root=str(export_root),
        target_root=str(target),
        dry_run=False,
    )

    if not target.exists() or not (target / ".git").is_dir():
        raise RuntimeError(f"Target path {target} is not a git repository")

    _run_git_command(["git", "checkout", branch], cwd=target)
    status_proc = _run_git_command(["git", "status", "--porcelain"], cwd=target, capture_output=True)
    if not status_proc.stdout.strip():
        return {
            "status": "skipped",
            "reason": "No changes to commit",
            "sync": sync_payload,
            "pipeline": pipeline_result.data,
        }

    _run_git_command(["git", "add", "-A"], cwd=target)

    version_info = pipeline_result.data.get("version", {}) if pipeline_result.data else {}
    new_version = version_info.get("new") or "unknown"
    message = commit_message or f"chore: sync aware-sdk {new_version}"

    _run_git_command(["git", "commit", "-m", message], cwd=target)
    rev_proc = _run_git_command(["git", "rev-parse", "HEAD"], cwd=target, capture_output=True)
    commit_sha = rev_proc.stdout.strip()

    if not skip_push:
        _run_git_command(["git", "push", "origin", branch], cwd=target)

    return {
        "status": "ok",
        "version": new_version,
        "commit": commit_sha,
        "message": message,
        "branch": branch,
        "pushed": not skip_push,
        "sync": sync_payload,
        "pipeline": pipeline_result.data,
    }


def _parse_pipeline_inputs(values: list[str]) -> Dict[str, List[str]]:
    inputs: Dict[str, List[str]] = {}
    for entry in values:
        if "=" not in entry:
            raise ValueError(f"Pipeline input must be key=value (got '{entry}')")
        key, raw_value = entry.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Pipeline input key cannot be empty.")
        inputs.setdefault(key, []).append(raw_value.strip())
    return inputs


def _resolve_pipeline_inputs(spec: PipelineSpec, provided: Dict[str, List[str]]) -> Dict[str, object]:
    resolved: Dict[str, object] = {}
    for name, input_spec in spec.inputs.items():
        values = provided.get(name, [])
        if input_spec.multiple:
            if values:
                resolved[name] = [value for value in values if value]
            elif input_spec.default is not None:
                default = input_spec.default
                if isinstance(default, (list, tuple)):
                    resolved[name] = [str(item) for item in default]
                else:
                    resolved[name] = [str(default)]
            elif input_spec.required:
                raise ValueError(f"Missing required pipeline input '{name}' for '{spec.slug}'.")
            else:
                resolved[name] = []
        else:
            value = values[-1] if values else input_spec.default
            if value is None and input_spec.required:
                raise ValueError(f"Missing required pipeline input '{name}' for '{spec.slug}'.")
            resolved[name] = value

    for name, values in provided.items():
        if name not in resolved:
            resolved[name] = values if len(values) != 1 else values[0]

    return resolved


def _parse_key_value_args(values: list[str]) -> dict[str, object]:
    options: dict[str, object] = {}
    for entry in values:
        if "=" not in entry:
            raise ValueError(f"Argument must be key=value (got '{entry}')")
        key, raw_value = entry.split("=", 1)
        options[key.strip()] = raw_value.strip()
    return options


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
