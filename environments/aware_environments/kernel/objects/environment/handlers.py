"""Kernel handlers for environment render/lock operations."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from aware_environment.fs import (
    EnsureInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    PatchInstruction,
    WriteInstruction,
)
from .._shared.patch import build_patch_instruction_from_text
from aware_environment.renderer import (
    render_environment_guide,
    render_role_bundle,
    render_rule_fragments,
    render_rules,
)
from aware_environment.doc.fragments import apply_fragments, render_fragments
from aware_environment import (
    Environment,
    compute_env_lock,
    compute_rules_lock,
    load_environment,
)
from aware_environment.object.spec import ObjectSpec, ObjectFunctionSpec
from .schemas import (
    RenderAgentPayload,
    RenderGuidePayload,
    RenderRolePayload,
    RenderRulePayload,
    RenderObjectPayload,
    RenderProtocolPayload,
    EnvironmentLockPayload,
    RulesLockPayload,
    DescribeEnvironmentPayload,
    ApplyPatchPayload,
)
from .guide_builder import build_agent_guide


@dataclass
class RenderResult:
    payload: object
    plan: OperationPlan | None = None


def _write_plan(
    *,
    context: OperationContext,
    content: str,
    path: Path,
    doc_type: str = "environment-doc",
    summary: str | None = None,
) -> OperationPlan:
    path = Path(path).resolve()
    ensures = (EnsureInstruction(path=path.parent),)
    timestamp = contextual_timestamp()

    if path.exists():
        original = path.read_text(encoding="utf-8")
        patch_instruction, _ = build_patch_instruction_from_text(
            path=path,
            original_text=original,
            updated_text=content,
            doc_type=doc_type,
            timestamp=timestamp,
            policy=OperationWritePolicy.MODIFIABLE,
            metadata={"path": str(path)},
            summary=summary or f"Updated {path.name}",
            event="modified",
        )
        patches = (patch_instruction,) if patch_instruction is not None else ()
        writes: tuple[WriteInstruction, ...] = ()
    else:
        patches = ()
        writes = (
            WriteInstruction(
                path=path,
                content=content,
                policy=OperationWritePolicy.MODIFIABLE,
                event="created",
                doc_type=doc_type,
                timestamp=timestamp,
                metadata={"path": str(path)},
            ),
        )

    return OperationPlan(
        context=context,
        ensure_dirs=ensures,
        writes=writes,
        patches=patches,
    )


def _plan_for_writes(
    *,
    context: OperationContext,
    content: str,
    writes: Sequence[Tuple[Path, str]],
) -> OperationPlan:
    ensure_dirs: Dict[Path, EnsureInstruction] = {}
    write_instructions: List[WriteInstruction] = []
    patch_instructions: List[PatchInstruction] = []
    timestamp = contextual_timestamp()

    for path, doc_type in writes:
        resolved = Path(path).resolve()
        ensure_dirs.setdefault(resolved.parent, EnsureInstruction(path=resolved.parent))
        if resolved.exists():
            original = resolved.read_text(encoding="utf-8")
            patch_instruction, _ = build_patch_instruction_from_text(
                path=resolved,
                original_text=original,
                updated_text=content,
                doc_type=doc_type,
                timestamp=timestamp,
                policy=OperationWritePolicy.MODIFIABLE,
                metadata={"path": str(resolved)},
                summary=f"Updated {resolved.name}",
                event="modified",
            )
            if patch_instruction is not None:
                patch_instructions.append(patch_instruction)
        else:
            write_instructions.append(
                WriteInstruction(
                    path=resolved,
                    content=content,
                    policy=OperationWritePolicy.MODIFIABLE,
                    event="created",
                    doc_type=doc_type,
                    timestamp=timestamp,
                    metadata={"path": str(resolved)},
                )
            )

    return OperationPlan(
        context=context,
        ensure_dirs=tuple(ensure_dirs.values()),
        writes=tuple(write_instructions),
        patches=tuple(patch_instructions),
    )


def apply_patch(
    *,
    path: Path,
    diff: str | None = None,
    diff_file: Path | None = None,
    policy: str = "modifiable",
    doc_type: str = "environment-doc",
    summary: str | None = None,
) -> RenderResult:
    resolved_path = Path(path).expanduser().resolve()

    if diff is not None and diff_file is not None:
        raise ValueError("Provide either --diff or --diff-file, not both.")
    if diff is None and diff_file is None:
        raise ValueError("Either --diff or --diff-file must be provided.")

    if diff_file:
        diff_path = Path(diff_file).expanduser().resolve()
        diff_text = diff_path.read_text(encoding="utf-8")
        diff_source = str(diff_path)
    else:
        diff_text = diff or ""
        diff_source = "inline"

    if not diff_text.strip():
        payload = ApplyPatchPayload(
            path=resolved_path,
            status="noop",
            summary=f"No changes detected for {resolved_path}",
            diff_hash=None,
        )
        return RenderResult(payload=payload, plan=None)

    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    try:
        policy_enum = OperationWritePolicy(policy)
    except ValueError as exc:
        raise ValueError(f"Unsupported patch policy '{policy}'.") from exc

    timestamp = contextual_timestamp()
    hook_metadata = {"diff_source": diff_source, "diff_hash": f"sha256:{diff_hash}"}
    if summary:
        hook_metadata.setdefault("summary", summary)

    patch_instruction = PatchInstruction(
        path=resolved_path,
        diff=diff_text,
        policy=policy_enum,
        doc_type=doc_type,
        timestamp=timestamp,
        metadata={"path": str(resolved_path)},
        hook_metadata=hook_metadata,
        summary=summary,
    )

    plan = OperationPlan(
        context=OperationContext(
            object_type="environment",
            function="apply-patch",
            selectors={"path": str(resolved_path)},
        ),
        patches=(patch_instruction,),
    )

    payload = ApplyPatchPayload(
        path=resolved_path,
        status="planned",
        summary=summary or f"Patched {resolved_path}",
        diff_hash=f"sha256:{diff_hash}",
    )
    return RenderResult(payload=payload, plan=plan)


def contextual_timestamp():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def render_agent(
    environment: Environment,
    *,
    agent: str,
    process: Optional[str],
    thread: Optional[str],
    identities_root: Path,
    heading_level: int = 1,
    context: Optional[Mapping[str, str]] = None,
    output_path: Optional[Path] = None,
    write: bool = True,
    omit_constitution: bool = False,
) -> RenderResult:
    canonical_path = (
        Path(identities_root)
        / "agents"
        / agent
        / "runtime"
        / "process"
        / (process or "main")
        / "threads"
        / (thread or "main")
        / "AGENT.md"
    )

    include_constitution = not omit_constitution
    guide = build_agent_guide(
        environment,
        agent=agent,
        process=process,
        thread=thread,
        identities_root=Path(identities_root),
        heading_level=heading_level,
        extra_context=context or {},
        include_constitution=include_constitution,
        include_identity=True,
    )

    target_path = Path(output_path) if output_path is not None else canonical_path
    mode = "write" if write else ("output" if output_path is not None else "stdout")

    context_info = OperationContext(
        object_type="environment",
        function="render-agent",
        selectors={
            "agent": agent,
            "process": process or "main",
            "thread": thread or "main",
            "include_constitution": str(include_constitution).lower(),
        },
    )
    plan: OperationPlan | None = None
    if write or output_path is not None:
        plan = _write_plan(
            context=context_info,
            content=guide.markdown,
            path=target_path,
        )

    payload = RenderAgentPayload(
        markdown=guide.markdown,
        output_path=target_path if (write or output_path is not None) else None,
        agent=agent,
        process=process,
        thread=thread,
        mode=mode,
        version_metadata=guide.version_metadata,
        session_snapshot=guide.session_snapshot,
        inspected_receipts=guide.inspected_receipts,
        workspace_paths=guide.workspace_paths,
        include_constitution=include_constitution,
    )
    return RenderResult(payload=payload, plan=plan)


def render_role(
    environment: Environment,
    *,
    roles: Iterable[str],
    heading_level: int = 2,
    output_path: Optional[Path] = None,
    write: bool = False,
) -> RenderResult:
    bundle = render_role_bundle(environment, role_slugs=tuple(roles)).strip()
    plan: OperationPlan | None = None
    if write:
        if output_path is None:
            raise ValueError("output_path required when write=True for render_role.")
        context = OperationContext(
            object_type="environment",
            function="render-role",
            selectors={"roles": ",".join(roles)},
        )
        plan = _write_plan(
            context=context,
            content=bundle + "\n",
            path=output_path,
        )
    payload = RenderRolePayload(markdown=bundle, output_path=output_path)
    return RenderResult(payload=payload, plan=plan)


def render_object(
    environment: Environment,
    *,
    object: str,
    heading_level: int = 2,
    output_path: Optional[Path] = None,
    write: bool = False,
) -> RenderResult:
    spec = environment.objects.get(object)
    if spec is None:
        available = ", ".join(sorted(environment.objects.keys()))
        raise ValueError(f"Unknown object '{object}'. Available objects: {available}.")

    markdown = _render_object_markdown(spec, heading_level=heading_level)
    target_path: Optional[Path] = None
    if write:
        if output_path is None:
            raise ValueError("output_path required when write=True for render_object.")
        target_path = Path(output_path)
    elif output_path is not None:
        target_path = Path(output_path)

    plan: OperationPlan | None = None
    selectors = {"object": object}
    if target_path is not None:
        context = OperationContext(
            object_type="environment",
            function="render-object",
            selectors=selectors,
        )
        plan = _write_plan(context=context, content=markdown, path=target_path)

    payload = RenderObjectPayload(
        markdown=markdown,
        output_path=target_path if target_path is not None else None,
        object=object,
        mode="write" if target_path is not None else "stdout",
    )
    return RenderResult(payload=payload, plan=plan)


def render_rule(
    environment: Environment,
    *,
    rule_ids: Iterable[str],
    fragments: bool = False,
    object_filter: Optional[Iterable[str]] = None,
    function_refs: Optional[Iterable[tuple[str, str]]] = None,
    heading_level: int = 1,
    output_path: Optional[Path] = None,
    write: bool = False,
) -> RenderResult:
    fragments_receipt = None
    if fragments:
        markdown = render_rule_fragments(
            environment,
            rule_ids=tuple(rule_ids),
            object_types=tuple(object_filter or ()),
            function_refs=tuple(function_refs or ()),
        ).strip()
    else:
        rule_ids_tuple = tuple(rule_ids)
        markdown = render_rules(environment, rule_ids_tuple).strip()
        selector_fragments = None
        if object_filter or function_refs:
            selector_fragments = render_fragments(
                environment,
                rule_ids=rule_ids_tuple,
                object_types=tuple(object_filter or ()),
                function_refs=tuple(function_refs or ()),
            )
        markdown, fragments_receipt = apply_fragments(
            markdown,
            fragments=selector_fragments,
            environment=environment,
        )
    plan: OperationPlan | None = None
    if write:
        if output_path is None:
            raise ValueError("output_path required when write=True for render_rule.")
        context = OperationContext(
            object_type="environment",
            function="render-rule",
            selectors={"rules": ",".join(rule_ids)},
        )
        plan = _write_plan(
            context=context,
            content=markdown if markdown.endswith("\n") else markdown + "\n",
            path=output_path,
        )
    fragments_payload = fragments_receipt.to_dict() if fragments_receipt is not None else None
    payload = RenderRulePayload(
        markdown=markdown,
        output_path=output_path,
        fragments_receipt=fragments_payload,
    )
    return RenderResult(payload=payload, plan=plan)


def render_protocol(
    environment: Environment,
    *,
    protocol_ids: Iterable[str],
    output_path: Optional[Path] = None,
    write: bool = False,
) -> RenderResult:
    slugs = tuple(protocol_ids)
    if not slugs:
        raise ValueError("At least one protocol id must be provided.")

    markdown_parts: List[str] = []
    resolved_paths: List[Path] = []
    for slug in slugs:
        try:
            protocol = environment.get_protocol(slug)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"Protocol '{slug}' not registered.") from exc
        if protocol is None:
            raise ValueError(f"Protocol '{slug}' not registered.")
        path = Path(protocol.path).resolve()
        if not path.exists():
            raise ValueError(f"Protocol '{slug}' content not found at {path}.")
        markdown_parts.append(path.read_text(encoding="utf-8").strip())
        resolved_paths.append(path)

    markdown = "\n\n".join(markdown_parts)
    plan: OperationPlan | None = None
    target_path: Optional[Path] = None

    if write:
        if output_path is None:
            if len(resolved_paths) != 1:
                raise ValueError("output_path required when writing multiple protocols.")
            target_path = resolved_paths[0]
        else:
            target_path = Path(output_path).expanduser().resolve()
        context = OperationContext(
            object_type="environment",
            function="render-protocol",
            selectors={"protocols": ",".join(slugs)},
        )
        plan = _write_plan(
            context=context,
            content=markdown + "\n",
            path=target_path,
        )
    elif output_path is not None:
        raise ValueError("output_path requires write=True for render_protocol.")

    payload = RenderProtocolPayload(
        markdown=markdown,
        output_path=target_path,
        protocols=list(slugs),
    )
    return RenderResult(payload=payload, plan=plan)


_GUIDE_PRIMARY_FILES: Tuple[str, ...] = ("AGENTS.md", "CLAUDE.md")
_GUIDE_CURSOR_FILE = ".cursorrules"


def render_guide(
    environment: Environment,
    *,
    aware_root: Path,
    heading_level: int = 1,
    write_primary: bool = True,
    write_cursorrules: bool = False,
    output_path: Optional[Path] = None,
    compose_agents: bool = False,
    default_agent: Optional[str] = None,
) -> RenderResult:
    aware_root_path = Path(aware_root).resolve()
    markdown = render_environment_guide(environment, heading_level=heading_level).strip()
    content = markdown + "\n"
    composed_agent_slug: Optional[str] = None
    if compose_agents:
        agent_slug = default_agent or "aware-manager"
        try:
            environment.agents.get(agent_slug)
        except Exception as exc:  # pragma: no cover - validation
            raise ValueError(f"Agent '{agent_slug}' not registered in environment.") from exc
        identities_root = aware_root_path / "docs" / "identities"
        if not identities_root.exists():  # pragma: no cover - validation
            raise ValueError(
                f"Identities root '{identities_root}' not found; cannot compose default agent persona."
            )
        agent_appendix = build_agent_guide(
            environment,
            agent=agent_slug,
            process=None,
            thread=None,
            identities_root=identities_root,
            heading_level=heading_level + 1,
            extra_context={},
            include_constitution=False,
            include_identity=False,
        ).markdown.strip()
        content = (
            content.rstrip()
            + f"\n\n## Default Agent Persona ({agent_slug})\n\n"
            + agent_appendix
            + "\n"
        )
        composed_agent_slug = agent_slug

    targets: List[Tuple[str, Path]] = []
    guide_outputs: Dict[str, str] = {}

    if output_path is not None:
        resolved_output = Path(output_path).resolve()
        targets.append(("custom-output", resolved_output))
        guide_outputs["custom-output"] = str(resolved_output)

    canonical_bundle: List[Path] = []
    if write_primary:
        for filename in _GUIDE_PRIMARY_FILES:
            path = aware_root_path / filename
            targets.append((filename, path))
            guide_outputs[filename] = str(path)
            canonical_bundle.append(path)

    should_write_cursor = write_primary or write_cursorrules
    cursor_path: Optional[Path] = None
    if should_write_cursor:
        cursor_path = aware_root_path / _GUIDE_CURSOR_FILE
        targets.append((_GUIDE_CURSOR_FILE, cursor_path))
        guide_outputs[_GUIDE_CURSOR_FILE] = str(cursor_path)
        if write_primary:
            canonical_bundle.append(cursor_path)

    if write_primary and canonical_bundle:
        guide_outputs["AGENTS_GUIDE"] = [str(path) for path in canonical_bundle]

    # Deduplicate targets by resolved path while preserving insertion order.
    unique_targets: Dict[Path, Tuple[str, Path]] = {}
    for label, path in targets:
        resolved = Path(path).resolve()
        unique_targets.setdefault(resolved, (label, resolved))

    plan: OperationPlan | None = None
    selectors = {"aware_root": str(aware_root_path)}
    if compose_agents:
        selectors["compose_agents"] = "true"
        if composed_agent_slug:
            selectors["default_agent"] = composed_agent_slug
            guide_outputs["default_agent_persona"] = composed_agent_slug

    if unique_targets:
        plan = _plan_for_writes(
            context=OperationContext(
                object_type="environment",
                function="render-guide",
                selectors=selectors,
            ),
            content=content,
            writes=[(path, "environment-guide") for _, path in unique_targets.values()],
        )

    payload = RenderGuidePayload(
        markdown=content.rstrip() + "\n",
        output_path=Path(output_path).resolve() if output_path is not None else None,
        written_paths=[path for _, path in unique_targets.values()],
        guide_outputs=guide_outputs,
    )
    return RenderResult(payload=payload, plan=plan)


def list_environments(environment: Environment) -> RenderResult:
    """Return a description of the kernel environment plus any active entrypoint."""

    kernel_entrypoint = "aware_environments.kernel.registry:get_environment"
    active_entrypoint = os.environ.get("AWARE_ENVIRONMENT_ENTRYPOINT")

    entries: List[Dict[str, Any]] = []

    def _describe_env(env: Environment | None) -> Dict[str, Any]:
        if env is None:
            return {}
        summary = describe(env).payload
        if hasattr(summary, "model_dump"):
            return summary.model_dump()  # type: ignore[attr-defined]
        if isinstance(summary, Mapping):  # pragma: no cover - defensive
            return dict(summary)
        return {}

    kernel_summary = _describe_env(environment)
    kernel_entry = {
        "id": "kernel",
        "entrypoint": kernel_entrypoint,
        "description": kernel_summary.get("title") or "Aware Kernel Environment",
        "source": "builtin",
        "active": active_entrypoint in (None, "", kernel_entrypoint),
        "load_error": None,
    }
    kernel_entry.update(kernel_summary)
    entries.append(kernel_entry)

    if active_entrypoint and active_entrypoint != kernel_entrypoint:
        try:
            active_env = load_environment(active_entrypoint)
            active_summary = _describe_env(active_env)
            description = active_summary.get("title") or "Aware Environment"
            load_error: Optional[str] = None
        except Exception as exc:  # pragma: no cover - defensive
            active_env = None
            active_summary = {}
            description = "Aware Environment"
            load_error = f"{exc.__class__.__name__}: {exc}"

        active_entry = {
            "id": "active",
            "entrypoint": active_entrypoint,
            "description": description,
            "source": "environment-variable",
            "active": True,
            "load_error": load_error,
        }
        active_entry.update(active_summary)
        entries.append(active_entry)

    return RenderResult(payload=entries, plan=None)


def environment_lock(
    environment: Environment,
    *,
    aware_root: Path,
    env_name: Optional[str] = None,
    kernel_ref: Optional[str] = None,
    version: Optional[str] = None,
    output_path: Optional[Path] = None,
    write: bool = True,
) -> RenderResult:
    aware_root_path = Path(aware_root or Path.cwd()).resolve()
    manifest = _read_json_file(aware_root_path / ".aware" / "environment.json")
    env_title = env_name or manifest.get("title") or "Aware Environment"
    resolved_version = version or _read_pyproject_version_file(aware_root_path / "environments" / "pyproject.toml")
    resolved_kernel_ref = kernel_ref or _git_revision_at(aware_root_path)

    lock = compute_env_lock(
        env_title,
        resolved_kernel_ref or "unknown",
        resolved_version or "unknown",
        environment,
    )

    targets: List[Tuple[str, Path]] = []
    canonical_path = aware_root_path / ".aware" / "ENV.lock"
    if write:
        targets.append(("ENV.lock", canonical_path))
    if output_path is not None:
        targets.append(("custom-output", Path(output_path).expanduser().resolve()))

    unique_targets: Dict[Path, Tuple[str, Path]] = {}
    for label, path in targets:
        resolved = Path(path).resolve()
        unique_targets.setdefault(resolved, (label, resolved))

    plan: OperationPlan | None = None
    if unique_targets:
        plan = _plan_for_writes(
            context=OperationContext(
                object_type="environment",
                function="environment-lock",
                selectors={"aware_root": str(aware_root_path)},
            ),
            content=json.dumps(lock, indent=2) + "\n",
            writes=[(path, "environment-lock") for _, path in unique_targets.values()],
        )

    written_paths = [path for _, path in unique_targets.values()]
    payload_output = canonical_path if write else (Path(output_path).expanduser().resolve() if output_path else None)
    payload = EnvironmentLockPayload(
        lock=lock,
        output_path=payload_output,
        written_paths=written_paths,
    )
    return RenderResult(payload=payload, plan=plan)


def rules_lock(
    environment: Environment,
    *,
    aware_root: Path,
    output_path: Optional[Path] = None,
    write: bool = True,
) -> RenderResult:
    aware_root_path = Path(aware_root or Path.cwd()).resolve()
    lock = compute_rules_lock(environment)

    targets: List[Tuple[str, Path]] = []
    canonical_path = aware_root_path / ".aware" / "RULES.lock"
    if write:
        targets.append(("RULES.lock", canonical_path))
    if output_path is not None:
        targets.append(("custom-output", Path(output_path).expanduser().resolve()))

    unique_targets: Dict[Path, Tuple[str, Path]] = {}
    for label, path in targets:
        resolved = Path(path).resolve()
        unique_targets.setdefault(resolved, (label, resolved))

    plan: OperationPlan | None = None
    if unique_targets:
        plan = _plan_for_writes(
            context=OperationContext(
                object_type="environment",
                function="rules-lock",
                selectors={"aware_root": str(aware_root_path)},
            ),
            content=json.dumps(lock, indent=2) + "\n",
            writes=[(path, "environment-rules-lock") for _, path in unique_targets.values()],
        )

    written_paths = [path for _, path in unique_targets.values()]
    payload_output = canonical_path if write else (Path(output_path).expanduser().resolve() if output_path else None)
    payload = RulesLockPayload(
        lock=lock,
        output_path=payload_output,
        written_paths=written_paths,
    )
    return RenderResult(payload=payload, plan=plan)


def describe(
    environment: Environment,
) -> RenderResult:
    rule = environment.get_constitution_rule()
    title = getattr(environment, "title", None)
    payload = DescribeEnvironmentPayload(
        title=title or "Aware Environment",
        constitution_rule=environment.constitution_rule_id,
        constitution_rule_title=rule.title if rule else None,
        agent_count=len(environment.agents.list()),
        role_count=len(environment.roles.list()),
        rule_count=len(environment.rules.list()),
        object_count=len(environment.objects.list()),
        agents=sorted(spec.slug for spec in environment.agents.list()),
        roles=sorted(spec.slug for spec in environment.roles.list()),
        rules=sorted(spec.id for spec in environment.rules.list()),
        objects=sorted(spec.type for spec in environment.objects.list()),
    )
    return RenderResult(payload=payload, plan=None)


def _read_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_pyproject_version_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    project = data.get("project")
    if isinstance(project, Mapping):
        version = project.get("version")
        if isinstance(version, str):
            return version
    return None


def _git_revision_at(base_path: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            cwd=str(base_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        return None
    revision = result.stdout.strip()
    return revision or None


__all__ = [
    "render_agent",
    "render_role",
    "render_rule",
    "render_object",
    "render_guide",
    "environment_lock",
    "rules_lock",
    "describe",
]
def _format_heading(level: int, text: str) -> str:
    level = max(1, level)
    return f"{'#' * level} {text}".rstrip()


def _format_table_row(cells: Iterable[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _markdown_for_arguments(arguments: Sequence[Mapping[str, object | None]]) -> list[str]:
    if not arguments:
        return []
    rows = [
        _format_table_row(["Flag(s)", "Name", "Required", "Multiple", "Default", "Help"]),
        _format_table_row(["---", "---", "---", "---", "---", "---"]),
    ]
    for descriptor in arguments:
        flags = ", ".join(descriptor.get("flags") or [])
        name = descriptor.get("name") or ""
        required = "yes" if descriptor.get("required") else ""
        multiple = "yes" if descriptor.get("multiple") else ""
        default = descriptor.get("default")
        if isinstance(default, bool):
            default = "true" if default else "false"
        elif default is None:
            default = ""
        else:
            default = str(default)
        help_text = descriptor.get("help") or ""
        rows.append(
            _format_table_row(
                [
                    f"`{flags}`" if flags else "",
                    f"`{name}`" if name else "",
                    required,
                    multiple,
                    f"`{default}`" if default else "",
                    help_text,
                ]
            )
        )
    return rows


def _render_object_markdown(spec: ObjectSpec, heading_level: int = 2) -> str:
    lines: list[str] = []
    level = max(1, heading_level)

    lines.append(_format_heading(level, f"Object `{spec.type}`"))
    if spec.description:
        lines.append("")
        lines.append(spec.description.strip())

    default_selectors = spec.metadata.get("default_selectors")
    if isinstance(default_selectors, Mapping) and default_selectors:
        lines.append("")
        lines.append(_format_heading(level + 1, "Default Selectors"))
        lines.append("")
        lines.append(_format_table_row(["Selector", "Default"]))
        lines.append(_format_table_row(["---", "---"]))
        for key, value in sorted(default_selectors.items()):
            lines.append(_format_table_row([f"`{key}`", f"`{value}`"]))

    if spec.pathspecs:
        lines.append("")
        lines.append(_format_heading(level + 1, "Pathspecs"))
        lines.append("")
        lines.append(_format_table_row(["ID", "Visibility", "Layout", "Instantiation", "Description"]))
        lines.append(_format_table_row(["---", "---", "---", "---", "---"]))
        for pathspec in spec.pathspecs:
            layout = "/".join(pathspec.layout_path)
            instantiation = "/".join(pathspec.instantiation_path)
            description = pathspec.description or ""
            lines.append(
                _format_table_row(
                    [
                        f"`{pathspec.id}`",
                        f"`{pathspec.visibility.value}`",
                        f"`{layout}`" if layout else "",
                        f"`{instantiation}`" if instantiation else "",
                        description,
                    ]
                )
            )

    if spec.functions:
        lines.append("")
        lines.append(_format_heading(level + 1, "Functions"))
        for function in sorted(spec.functions, key=lambda f: f.name):
            lines.append("")
            lines.append(_format_heading(level + 2, f"`{function.name}`"))

            function_description = function.description or function.metadata.get("description") or ""
            if function_description:
                lines.append("")
                lines.append(function_description.strip())

            selectors_meta = function.metadata.get("selectors") or ()
            if selectors_meta:
                lines.append("")
                selectors_display = ", ".join(f"`{selector}`" for selector in selectors_meta)
                lines.append(f"**Selectors:** {selectors_display}")

            rule_ids = function.metadata.get("rule_ids") or ()
            if rule_ids:
                lines.append("")
                rules_display = ", ".join(f"`{rule}`" for rule in rule_ids)
                lines.append(f"**Rule IDs:** {rules_display}")

            pathspec_refs = function.metadata.get("pathspecs") or {}
            if pathspec_refs:
                lines.append("")
                lines.append("**Pathspecs:**")
                for scope, refs in pathspec_refs.items():
                    if not refs:
                        continue
                    refs_display = ", ".join(f"`{ref}`" for ref in refs)
                    lines.append(f"- {scope}: {refs_display}")

            argument_descriptors = function.metadata.get("arguments") or ()
            argument_rows = _markdown_for_arguments(argument_descriptors)
            if argument_rows:
                lines.append("")
                lines.extend(argument_rows)

            examples = function.examples or function.metadata.get("examples") or ()
            if examples:
                lines.append("")
                lines.append("**Examples:**")
                for example in examples:
                    lines.append(f"- `{example}`")

    return "\n".join(lines).strip() + "\n"
