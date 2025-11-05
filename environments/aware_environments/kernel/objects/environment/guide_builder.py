from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from aware_environment import compute_env_lock, compute_rules_lock, Environment
from aware_environment.pathspec import PathSpec, PathSpecResolutionError
from aware_environment.renderer import render_constitution_summary, render_role_bundle


CAPABILITY_REFS: Tuple[Tuple[str, str], ...] = (
    ("agent", "signup"),
    ("agent", "create-process"),
    ("agent", "create-thread"),
    ("agent", "whoami"),
    ("agent-thread", "signup"),
    ("agent-thread", "login"),
    ("agent-thread", "session-update"),
    ("agent-thread-memory", "status"),
    ("agent-thread-memory", "history"),
    ("agent-thread-memory", "write-working"),
    ("agent-thread-memory", "append-episodic"),
    ("agent-thread-memory", "diff"),
    ("agent-thread-memory", "validate"),
    ("environment", "render-agent"),
    ("environment", "render-role"),
    ("environment", "render-rule"),
)

MISSION_BULLETS: Tuple[str, ...] = (
    "Establish a shared thread/object/agent contract for every environment participant.",
    "Surface thread/object interactions consistently across Studio panes and provider terminals.",
    "Keep receipts as the single source of truth: threads do not mutate state, agents act via objects, every mutation emits a receipt.",
)

OPERATING_CHECKLIST: Tuple[str, ...] = (
    "Select and confirm your thread via CLI (`aware-cli object list/status --type thread`) before invoking domain objects.",
    "Bind yourself (or your provider) to the thread with `thread.participants-bind`; every action must cite the active binding.",
    "Execute object functions only through environment handlers (CLI/Studio); every mutation must emit a receipt bound to the selected thread.",
    "Capture receipt identifiers in working memory within 30 minutes and cite them in responses.",
    "Work inside the three-window layout: Orchestration (left), Desktop (center), Execution (right) to keep context aligned.",
    "Follow `Rule 01-thread-01-runtime` for thread operations and `Rule 02-task-01-lifecycle` for task execution flows.",
)


@dataclass
class AgentGuideData:
    markdown: str
    version_metadata: Dict[str, Any]
    session_snapshot: Dict[str, Any]
    inspected_receipts: List[Dict[str, Any]]
    workspace_paths: Dict[str, str]


def build_agent_guide(
    environment: Environment,
    *,
    agent: str,
    process: Optional[str],
    thread: Optional[str],
    identities_root: Path,
    heading_level: int = 1,
    extra_context: Optional[Mapping[str, str]] = None,
    include_constitution: bool = True,
    include_identity: bool = True,
) -> AgentGuideData:
    agent_dir = identities_root / "agents" / agent
    process_dir = (
        agent_dir / "runtime" / "process" / process if process else None
    )
    thread_dir = (
        process_dir / "threads" / thread if process_dir is not None and thread else None
    )

    agent_doc = _read_json(agent_dir / "agent.json")
    process_doc = _read_json(process_dir / "process.json") if process_dir else None
    thread_doc = (
        _read_json(thread_dir / "agent_process_thread.json") if thread_dir else None
    )

    agent_id = (
        agent_doc.get("id") if isinstance(agent_doc, Mapping) else None
    )
    identity_label = _identity_label(agent_doc, agent, agent_id)

    actor_id = (
        thread_doc.get("actor_id") if isinstance(thread_doc, Mapping) else None
    )

    title = "/".join([part for part in (agent, process, thread) if part])
    base_level = max(1, min(int(heading_level or 1), 6))
    section_level = min(base_level + 1, 6)
    subsection_level = min(section_level + 1, 6)
    heading_token = "#" * base_level
    section_token = "#" * section_level
    subsection_token = "#" * subsection_level

    lines: List[str] = [f"{heading_token} Agent Rulebook · {title}", ""]

    lines.append(f"{section_token} Mission & Invariants")
    lines.append("")
    for bullet in MISSION_BULLETS:
        lines.append(f"- {bullet}")

    lines.append("")
    lines.append(f"{section_token} Operating Checklist")
    lines.append("")
    for index, item in enumerate(OPERATING_CHECKLIST, start=1):
        lines.append(f"{index}. {item}")

    if include_identity:
        lines.append("")
        lines.append(f"{section_token} Identity Context")
        lines.append("")
        lines.append(f"- **Agent slug:** `{agent}`")
        if identity_label:
            lines.append(f"- **Identity:** `{identity_label}`")
        if agent_id:
            lines.append(f"- **Agent ID:** `{agent_id}`")
        if isinstance(actor_id, str) and actor_id:
            lines.append(f"- **Actor ID:** `{actor_id}`")
        if process:
            lines.append(f"- **Process:** `{process}`")
        if thread:
            lines.append(f"- **Thread:** `{thread}`")
        if extra_context:
            for key, value in extra_context.items():
                lines.append(f"- **{key}:** `{value}`")

    if include_identity and process and thread:
        lines.extend(
            [
                "",
                f"{section_token} Local Context",
                "",
                "- Working memory: ./working_memory.md",
                "- Episodic entries: ./episodic/",
                "- Role registry: ./roles.json",
            ]
        )
        lines.append("")

    agent_spec = None
    try:
        agent_spec = environment.agents.get(agent)
    except Exception:
        agent_spec = None

    role_slugs: Tuple[str, ...] = tuple(agent_spec.role_slugs) if agent_spec else ()
    role_bundle = (
        render_role_bundle(environment, role_slugs).strip() if role_slugs else ""
    )
    lines.append("")
    lines.append(f"{section_token} Roles & Policies")
    lines.append("")
    if role_bundle:
        lines.append(role_bundle)
    else:
        lines.append("_Agent has no roles defined._")

    if include_constitution:
        lines.extend(["", "---", "", f"{section_token} Appendix A · Environment Constitution", ""])
        constitution = _constitution_body(environment, heading_level=subsection_level)
        if constitution:
            lines.append(constitution)
        else:
            lines.append("_Constitution rule not configured._")

    selectors = {"agent": agent}
    if include_identity:
        if process:
            selectors["process"] = process
        if thread:
            selectors["thread"] = thread

    workspace_section, workspace_paths = _workspace_contract_section(
        environment, identities_root, selectors if include_identity else {"agent": agent}
    )
    appendix_b: List[str] = []
    if workspace_section:
        appendix_b.extend(_retitle_section(workspace_section, f"{subsection_token} Workspace Contract"))
    capabilities_section = _capabilities_section(environment, CAPABILITY_REFS)
    if capabilities_section:
        appendix_b.extend(_retitle_section(capabilities_section, f"{subsection_token} Capabilities"))
    if appendix_b:
        lines.extend(["", f"{section_token} Appendix{' B' if include_constitution else ' A'} · Workspace & Capabilities", ""] + appendix_b)

    session_section, session_snapshot = _session_snapshot_section(
        identities_root=identities_root,
        agent=agent,
        process=process,
        thread=thread,
        thread_metadata=thread_doc if isinstance(thread_doc, Mapping) else {},
    )
    appendix_c: List[str] = []
    if session_section:
        appendix_c.extend(_retitle_section(session_section, f"{subsection_token} Session Snapshot"))
    receipts_data = _load_recent_receipts()
    receipts_section = _receipts_section(receipts_data)
    if receipts_section:
        lines.extend(
            [
                "",
                f"{section_token} Appendix{' C' if include_constitution else ' B'} · Receipts",
                "",
            ]
            + _retitle_section(receipts_section, f"{subsection_token} Recent Receipts")
        )

    safety_section = _safety_bounds_section(
        thread_doc if isinstance(thread_doc, Mapping) else {}
    )
    if safety_section:
        appendix_c.extend(_retitle_section(safety_section, f"{subsection_token} Safety Bounds"))
    if appendix_c:
        lines.extend(["", f"{section_token} Appendix{' D' if include_constitution else ' C'} · Runtime", ""] + appendix_c)

    version_section, version_metadata = _version_metadata_section(environment)
    usage_section = _usage_quickstart_section(agent, process, thread)
    appendix_e: List[str] = []
    if version_section:
        appendix_e.extend(_retitle_section(version_section, f"{subsection_token} Version Metadata"))
    if usage_section:
        appendix_e.extend(_retitle_section(usage_section, f"{subsection_token} CLI Quickstart"))
    if appendix_e:
        lines.extend(["", f"{section_token} Appendix{' E' if include_constitution else ' D'} · References", ""] + appendix_e)

    markdown = "\n".join(line for line in lines if line is not None).strip() + "\n"
    inspected_receipts = _sanitise_receipts(receipts_data)

    return AgentGuideData(
        markdown=markdown,
        version_metadata=version_metadata,
        session_snapshot=session_snapshot,
        inspected_receipts=inspected_receipts,
        workspace_paths=workspace_paths,
    )


def _constitution_body(environment: Environment, heading_level: int) -> str:
    try:
        return render_constitution_summary(environment, heading_level=heading_level).strip()
    except Exception:
        return ""


def _retitle_section(lines: Sequence[str], heading: str) -> List[str]:
    mutable = list(lines)
    for index, line in enumerate(mutable):
        if line.strip():
            mutable[index] = heading
            break
    return mutable


def _workspace_contract_section(
    environment: Environment,
    identities_root: Path,
    selectors: Mapping[str, str],
) -> Tuple[List[str], Dict[str, str]]:
    try:
        spec = environment.objects.get("environment")
    except Exception:
        return [], {}
    pathspecs: Sequence[PathSpec] = spec.pathspecs or ()
    if not pathspecs:
        return [], {}

    resolved_paths: Dict[str, str] = {}
    for pathspec in pathspecs:
        try:
            resolved = pathspec.instantiate(
                identities_root,
                selectors=selectors,
                private_root=identities_root,
            )
        except PathSpecResolutionError:
            continue
        resolved_paths[pathspec.id] = _relative_path(resolved, identities_root)

    lines: List[str] = [
        "## Workspace Contract",
        "",
        "| PathSpec | Layout | Visibility | Operations | Description |",
        "| --- | --- | --- | --- | --- |",
    ]
    operations_map = _environment_pathspec_operations(spec)
    for pathspec in pathspecs:
        operations = operations_map.get(pathspec.id, ())
        description = pathspec.description or "_None_"
        lines.append(
            f"| `{pathspec.id}` | `{_format_layout(pathspec)}` | `{pathspec.visibility.value}` | "
            f"{_format_operations(operations)} | {description} |"
        )
    lines.append("")
    if resolved_paths:
        lines.append("_Resolved paths (relative to identities root):_")
        for spec_id in sorted(resolved_paths):
            lines.append(f"- `{spec_id}` → `{resolved_paths[spec_id]}`")
        lines.append("")
    return lines, resolved_paths


def _capabilities_section(
    environment: Environment,
    capability_refs: Sequence[Tuple[str, str]],
) -> List[str]:
    rows: List[str] = []
    for object_type, function_name in capability_refs:
        try:
            spec = environment.objects.get(object_type)
        except Exception:
            continue
        kernel_func = next(
            (func for func in spec.functions if func.name == function_name),
            None,
        )
        description = ""
        if kernel_func is not None:
            description = kernel_func.description or ""
        operations = _function_operations(spec, function_name)
        selectors = kernel_func.metadata.get("selectors") if kernel_func else ()
        selector_text = _format_selectors(selectors)
        rules = _function_rule_ids(kernel_func)
        capability_label = f"`{object_type}.{function_name}`"
        rows.append(
            f"| {capability_label} | {description or '_No summary provided._'} | "
            f"{_format_operations(operations)}; selectors: {selector_text} | {rules} |"
        )
    if not rows:
        return []
    lines: List[str] = ["## Capabilities", "", "| Capability | Summary | I/O | Access |", "| --- | --- | --- | --- |"]
    lines.extend(rows)
    lines.append("")
    return lines


def _session_snapshot_section(
    *,
    identities_root: Path,
    agent: str,
    process: Optional[str],
    thread: Optional[str],
    thread_metadata: Mapping[str, Any],
) -> Tuple[List[str], Dict[str, Any]]:
    env_metadata = _metadata_from_env()
    sources: List[str] = []
    if any(env_metadata.values()):
        sources.append("env")

    target_parts = [agent]
    if process:
        target_parts.append(process)
    if thread:
        target_parts.append(thread)
    target = "/".join(target_parts)

    terminal_info = env_metadata.get("terminal") or {}
    session_snapshot: Dict[str, Any] = {
        "target": target,
        "actor_id": thread_metadata.get("actor_id"),
        "provider": env_metadata.get("provider"),
        "session_id": env_metadata.get("provider_session"),
        "terminal_id": env_metadata.get("terminal_id"),
        "apt_id": env_metadata.get("apt_id"),
    }

    agent_identity_path = identities_root / "agents" / agent / "agent.json"
    if agent_identity_path.exists():
        sources.append("filesystem")

    lines: List[str] = [
        "## Session Snapshot",
        "",
        f"- **Target:** `{target}`",
        f"- **Actor ID:** `{session_snapshot.get('actor_id')}`"
        if session_snapshot.get("actor_id")
        else "- **Actor ID:** _Not recorded_",
        f"- **Provider:** `{session_snapshot.get('provider')}`"
        if session_snapshot.get("provider")
        else "- **Provider:** _Not bound_",
        f"- **Session ID:** `{session_snapshot.get('session_id')}`"
        if session_snapshot.get("session_id")
        else "- **Session ID:** _Not bound_",
        f"- **Terminal ID:** `{session_snapshot.get('terminal_id')}`"
        if session_snapshot.get("terminal_id")
        else "- **Terminal ID:** _Not bound_",
        f"- **APT ID:** `{session_snapshot.get('apt_id')}`"
        if session_snapshot.get("apt_id")
        else "- **APT ID:** _Not bound_",
    ]
    if sources:
        unique_sources = ", ".join(sorted(set(sources)))
        lines.append(f"- **Sources:** {unique_sources}")
        session_snapshot["sources"] = unique_sources

    terminal_sessions = terminal_info.get("sessions") if isinstance(terminal_info, Mapping) else None
    if isinstance(terminal_sessions, Sequence) and terminal_sessions:
        lines.extend(
            [
                "",
                "| Session | Status | Thread | Updated |",
                "| --- | --- | --- | --- |",
            ]
        )
        for entry in terminal_sessions:
            if not isinstance(entry, Mapping):
                continue
            session_id = entry.get("session_id") or "_unknown_"
            status = entry.get("status") or "_unknown_"
            thread_id = entry.get("thread_id") or "_unknown_"
            updated_at = entry.get("updated_at") or "_unknown_"
            lines.append(f"| `{session_id}` | {status} | {thread_id} | {updated_at} |")
        lines.append("")
    return lines, session_snapshot


def _load_recent_receipts(limit: int = 3) -> List[Dict[str, Any]]:
    base = _aware_home()
    receipts: List[Dict[str, Any]] = []

    identity_dir = base / "receipts" / "identity"
    if identity_dir.exists():
        for path in sorted(identity_dir.glob("*.json")):
            data = _read_json(path)
            if not data:
                continue
            timestamp = (
                data.get("timestamp")
                or data.get("created_at")
                or data.get("updated_at")
                or datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z"
            )
            receipts.append(
                {
                    "kind": "identity",
                    "path": path,
                    "timestamp": timestamp,
                    "summary": data.get("action") or data.get("type"),
                    "data": data,
                }
            )

    if not receipts:
        sessions_dir = base / "sessions"
        if sessions_dir.exists():
            for path in sorted(sessions_dir.glob("*.json")):
                if path.name == "current_session.json":
                    continue
                data = _read_json(path)
                if not data:
                    continue
                timestamp = (
                    data.get("updated_at")
                    or data.get("created_at")
                    or datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z"
                )
                receipts.append(
                    {
                        "kind": "session",
                        "path": path,
                        "timestamp": timestamp,
                        "summary": f"session {data.get('status') or 'unknown'}",
                        "data": data,
                    }
                )

    receipts.sort(
        key=lambda entry: (
            _parse_iso8601(entry.get("timestamp")) or datetime.min,
            str(entry.get("path")),
        ),
        reverse=True,
    )
    return receipts[:limit]


def _receipts_section(receipts: Sequence[Mapping[str, Any]]) -> List[str]:
    lines: List[str] = ["## Recent Receipts", ""]
    if not receipts:
        lines.append("_No receipts located under ~/.aware/receipts or ~/.aware/sessions._")
        lines.append("")
        return lines
    lines.extend(
        [
            "| Kind | Timestamp | Path | Summary |",
            "| --- | --- | --- | --- |",
        ]
    )
    base = _aware_home()
    for entry in receipts:
        kind = entry.get("kind") or "unknown"
        timestamp = entry.get("timestamp") or "unknown"
        path = entry.get("path")
        path_display = (
            _relative_path(path, base) if isinstance(path, Path) else str(path)
        )
        summary = entry.get("summary") or "_None_"
        lines.append(f"| `{kind}` | `{timestamp}` | `{path_display}` | {summary} |")
    lines.append("")
    return lines


def _safety_bounds_section(thread_metadata: Mapping[str, Any]) -> List[str]:
    iteration_count = thread_metadata.get("iteration_count")
    tool_retry_count = thread_metadata.get("tool_retry_count")
    lines: List[str] = [
        "## Safety Bounds",
        "",
        "- **Max operations per session:** _Not specified; follow provider policies and Rule 01 escalation._",
        "- **Max runtime per session:** _Monitor provider session receipts; escalate if runtime exceeds expected envelopes._",
        "- **Max token budget:** _Not declared; adhere to provider defaults and memory baseline guidance._",
        "- **Escalation policy:** _Escalate via terminal attach + Control Center; cite Rule 01 + Rule 04._",
    ]
    if iteration_count is not None or tool_retry_count is not None:
        lines.append("")
        lines.append("Thread runtime counters (current run):")
        if iteration_count is not None:
            lines.append(f"- Iteration count: {iteration_count}")
        if tool_retry_count is not None:
            lines.append(f"- Tool retry count: {tool_retry_count}")
    lines.append("")
    return lines


def _version_metadata_section(environment: Environment) -> Tuple[List[str], Dict[str, Any]]:
    env_manifest_path = Path(".aware") / "environment.json"
    environment_manifest = {}
    if env_manifest_path.exists():
        environment_manifest = _read_json(env_manifest_path) or {}

    env_title = environment_manifest.get("title") or "Aware Environment"
    env_id = environment_manifest.get("id")
    env_created = environment_manifest.get("created_at")

    env_version = _read_pyproject_version(Path("environments") / "pyproject.toml")
    cli_version = _read_pyproject_version(Path("tools") / "cli" / "pyproject.toml")
    kernel_ref = _git_revision()

    env_lock = compute_env_lock(
        env_title,
        kernel_ref or "unknown",
        env_version or "unknown",
        environment,
    )
    rules_lock = compute_rules_lock(environment)
    rules_digest = hashlib.sha256(json.dumps(rules_lock, sort_keys=True).encode("utf-8")).hexdigest()

    metadata = {
        "environment_title": env_title,
        "environment_id": env_id,
        "environment_created_at": env_created,
        "environment_version": env_version,
        "kernel_ref": kernel_ref,
        "environment_spec_hash": env_lock.get("spec_hash"),
        "rules_digest": rules_digest,
        "rules_count": len(rules_lock.get("rules", [])),
        "aware_cli_version": cli_version,
    }

    lines: List[str] = [
        "## Version Metadata",
        "",
        f"- **Environment:** {env_title}",
    ]
    if env_id:
        lines.append(f"- **Environment ID:** `{env_id}`")
    if env_created:
        lines.append(f"- **Environment created at:** `{env_created}`")
    lines.append(
        f"- **Environment version:** `{env_version}`" if env_version else "- **Environment version:** _Unknown_"
    )
    lines.append(f"- **aware-cli version:** `{cli_version}`" if cli_version else "- **aware-cli version:** _Unknown_")
    lines.append(f"- **Kernel ref:** `{kernel_ref}`" if kernel_ref else "- **Kernel ref:** _Unknown_")
    lines.append(f"- **Environment spec hash:** `{env_lock.get('spec_hash')}`")
    lines.append(f"- **RULES.lock digest:** `{rules_digest}` ({metadata['rules_count']} rules)")
    lines.append("")
    return lines, metadata


def _usage_quickstart_section(
    agent: str,
    process: Optional[str],
    thread: Optional[str],
) -> List[str]:
    process_display = process or "<process>"
    thread_display = thread or "<thread>"
    lines: List[str] = [
        "## Usage Quickstart",
        "",
        "1. Provision identity scaffolds:",
        "```bash",
        f"aware-cli object call --type agent --function signup --agent {agent} --process {process_display} --thread {thread_display}",
        "```",
        "2. Attach a provider session (replace `<provider>` as needed):",
        "```bash",
        f"aware-cli object call --type agent-thread --function login --id {agent}/{process_display}/{thread_display} "
        f"--provider <provider> --terminal-id term-main --ensure-terminal",
        "```",
        "3. Inspect bindings:",
        "```bash",
        "aware-cli object call --type agent --function whoami",
        "```",
        "4. Refresh the agent guide:",
        "```bash",
        f"aware-cli object call --type environment --id environment --function render-agent --agent {agent} "
        f"--process {process_display} --thread {thread_display} --write",
        "```",
        "5. Optional: emit guide to a custom path:",
        "```bash",
        f"aware-cli object call --type environment --id environment --function render-agent --agent {agent} "
        f"--process {process_display} --thread {thread_display} --out ./AGENT.md",
        "```",
        "6. Attach to running terminal (Control Center):",
        "```bash",
        f"aware-cli object call --type terminal --function attach --thread {agent}/{process_display}/{thread_display}",
        "```",
        "",
    ]
    return lines


def _environment_pathspec_operations(spec) -> Dict[str, Tuple[str, ...]]:
    operations: Dict[str, set[str]] = defaultdict(set)
    function = next((func for func in spec.functions if func.name == "render-agent"), None)
    metadata = function.metadata if function else {}
    pathspecs_meta = metadata.get("pathspecs")
    if isinstance(pathspecs_meta, Mapping):
        for category, spec_ids in pathspecs_meta.items():
            for spec_id in _flatten_pathspec_ids(spec_ids):
                operations[str(spec_id)].add(str(category))
    ordered: Dict[str, Tuple[str, ...]] = {}
    for spec_id, categories in operations.items():
        ordered[spec_id] = tuple(sorted(categories))
    return ordered


def _function_operations(spec, function_name: str) -> Tuple[str, ...]:
    kernel_function = next((func for func in spec.functions if func.name == function_name), None)
    if kernel_function is None:
        return tuple()
    metadata = kernel_function.metadata or {}
    pathspecs_meta = metadata.get("pathspecs")
    operations: List[str] = []
    if isinstance(pathspecs_meta, Mapping):
        for category, spec_ids in pathspecs_meta.items():
            if _flatten_pathspec_ids(spec_ids):
                operations.append(str(category))
    return tuple(sorted(set(operations)))


def _function_rule_ids(kernel_function) -> str:
    if kernel_function is None:
        return "_None_"
    rule_ids = kernel_function.metadata.get("rule_ids") if kernel_function.metadata else None
    if isinstance(rule_ids, str):
        return f"`{rule_ids}`"
    if isinstance(rule_ids, Sequence):
        items = ", ".join(f"`{rule}`" for rule in rule_ids)
        return items or "_None_"
    return "_None_"


def _format_operations(operations: Iterable[str]) -> str:
    items = list(operations)
    if not items:
        return "_None_"
    return ", ".join(f"`{item}`" for item in items)


def _format_selectors(value: Any) -> str:
    if value is None:
        return "_None_"
    if isinstance(value, str):
        return f"`{value}`"
    if isinstance(value, Sequence):
        return ", ".join(f"`{str(item)}`" for item in value)
    return f"`{value}`"


def _environment_spec(environment: Environment) -> Any:
    return environment.objects.get("environment")


def _flatten_pathspec_ids(source: Any) -> List[str]:
    if source is None:
        return []
    if isinstance(source, (list, tuple, set)):
        result: List[str] = []
        for value in source:
            result.extend(_flatten_pathspec_ids(value))
        return result
    if isinstance(source, Mapping):
        result: List[str] = []
        for value in source.values():
            result.extend(_flatten_pathspec_ids(value))
        return result
    return [str(source)]


def _format_layout(pathspec: PathSpec) -> str:
    return "/".join(pathspec.layout_path) if pathspec.layout_path else "."


def _identity_label(agent_identity: Optional[Mapping[str, Any]], agent_slug: str, agent_id: Optional[str]) -> str:
    if isinstance(agent_identity, Mapping):
        name = agent_identity.get("name")
        if isinstance(name, str) and name.strip():
            return name
    if agent_id:
        return agent_id
    return agent_slug


def _read_json(path: Path) -> Optional[dict]:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _relative_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _warenv(key: str) -> Optional[str]:
    value = os.environ.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _metadata_from_env() -> Dict[str, Optional[str]]:
    provider = _warenv("AWARE_PROVIDER")
    terminal_id = _warenv("AWARE_TERMINAL_ID")
    provider_session = _warenv("AWARE_PROVIDER_SESSION_ID") or _warenv("AWARE_SESSION_ID")
    data = {
        "agent": _warenv("AWARE_AGENT"),
        "process": _warenv("AWARE_PROCESS"),
        "thread": _warenv("AWARE_THREAD"),
        "apt_id": _warenv("APT_ID") or _warenv("AWARE_APT_ID"),
        "terminal_id": terminal_id,
        "provider": provider,
        "provider_session": provider_session,
    }
    if terminal_id or provider:
        data["terminal"] = {"id": terminal_id, "provider": provider}
    else:
        data["terminal"] = {}
    return data


def _aware_home() -> Path:
    custom = os.environ.get("AWARE_HOME")
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".aware"


def _read_pyproject_version(path: Path) -> Optional[str]:
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


def _git_revision() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        return None
    revision = result.stdout.strip()
    return revision or None


def _sanitise_receipts(receipts: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    sanitized: List[Dict[str, Any]] = []
    for entry in receipts:
        path_value = entry.get("path")
        if isinstance(path_value, Path):
            path_str = str(path_value)
        else:
            path_str = str(path_value) if path_value is not None else None
        data_value = entry.get("data")
        data_dict = dict(data_value) if isinstance(data_value, Mapping) else None
        sanitized.append(
            {
                "kind": entry.get("kind"),
                "timestamp": entry.get("timestamp"),
                "path": path_str,
                "summary": entry.get("summary"),
                "data": data_dict,
            }
        )
    return sanitized
