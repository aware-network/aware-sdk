"""Renderer helpers for environment-aware artifacts (rules, roles, agents)."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple

from .environment import Environment
from .exceptions import UnknownSpecError
from .object.spec import ObjectFunctionSpec, ObjectSpec
from .pathspec import PathSpec
from .role.spec import RoleSpec
from .rule.spec import RuleSpec
from .protocol.spec import ProtocolSpec

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Shared structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceEntry:
    """Lightweight representation of an object function for documentation."""

    group: str
    name: str
    summary: str
    selectors: Tuple[str, ...]
    flags: Tuple[Tuple[str, str], ...]
    examples: Tuple[str, ...]
    policy: str
    object_type: Optional[str] = None
    function: Optional[str] = None
    rule_ids: Tuple[str, ...] = ()
    hooks: Tuple[str, ...] = ()


def render_constitution_summary(environment: Environment, heading_level: int = 2) -> str:
    """Render the environment constitution rule."""

    rule = environment.get_constitution_rule()
    if rule is None:
        raise ValueError("Environment constitution rule not configured.")

    heading_level = max(1, min(int(heading_level or 1), 6))
    heading = "#" * heading_level
    title = rule.title or rule.id
    body = _strip_leading_heading(_read_rule_body(rule).strip())
    return f"{heading} {title}\n\n{body}\n"


def render_environment_guide(environment: Environment, heading_level: int = 1) -> str:
    """Render the environment guide including constitution metadata."""

    summary = render_constitution_summary(environment, heading_level).strip()

    if "\n" in summary:
        first_line, remainder = summary.split("\n", 1)
        remainder = remainder.lstrip("\n")
    else:
        first_line, remainder = summary, ""

    constitution = environment.get_constitution_rule()
    version_display = (
        constitution.version if constitution and constitution.version else environment.constitution_rule_id
    )
    metadata_block = f"**Constitution Version:** {version_display}"

    guide_parts = [first_line, "", metadata_block]
    if remainder:
        guide_parts.extend(["", remainder])

    return "\n".join(part for part in guide_parts) + "\n"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _policy_display(entry: ReferenceEntry) -> str:
    if entry.rule_ids:
        return ", ".join(f"`{rule_id}`" for rule_id in entry.rule_ids)
    return f"`{entry.policy}`" if entry.policy else "_None_"


def _selectors_display(selectors: Sequence[str]) -> str:
    if not selectors:
        return "_None_"
    return ", ".join(f"`{selector}`" for selector in selectors)


def _render_group_table(entries: Iterable[ReferenceEntry], *, show_policy: bool) -> List[str]:
    lines: List[str] = []
    if show_policy:
        lines.append("| Function | Summary | Policy |")
        lines.append("| --- | --- | --- |")
    else:
        lines.append("| Function | Summary |")
        lines.append("| --- | --- |")

    for entry in entries:
        if show_policy:
            lines.append(f"| `{entry.name}` | {entry.summary} | {_policy_display(entry)} |")
        else:
            lines.append(f"| `{entry.name}` | {entry.summary} |")
    lines.append("")
    return lines


def _render_entry_details(
    entry: ReferenceEntry,
    *,
    heading: Optional[str] = None,
    show_policy: bool = True,
    show_flags: bool = True,
    show_selectors: bool = True,
    show_examples: bool = True,
) -> List[str]:
    lines: List[str] = []
    lines.append(heading or f"#### `{entry.name}`")
    lines.append(entry.summary if entry.summary else "_No summary provided._")
    if show_policy:
        lines.append(f"**Policy:** {_policy_display(entry)}")
    if show_selectors:
        selector_text = _selectors_display(entry.selectors)
        lines.append(f"**Selectors:** {selector_text}")
    if show_flags:
        if entry.flags:
            lines.append("**Flags:**")
            for flag, description in entry.flags:
                lines.append(f"- `{flag}` — {description}")
        else:
            lines.append("**Flags:** _None_")
    elif entry.flags:
        lines.append("**Flags:**")
        for flag, description in entry.flags:
            lines.append(f"- `{flag}` — {description}")

    if entry.hooks:
        hooks_text = ", ".join(f"`{hook}`" for hook in entry.hooks)
        lines.append(f"**Hooks:** {hooks_text}")
    else:
        lines.append("**Hooks:** _None_")

    if show_examples and entry.examples:
        lines.append("**Examples:**")
        for example in entry.examples:
            lines.append("```bash")
            lines.append(example)
            lines.append("```")
    lines.append("")
    return lines


def _render_section_lines(
    entries: Sequence[ReferenceEntry],
    *,
    heading: Optional[str] = None,
    include_table: bool = True,
    show_policy: bool = True,
    show_flags: bool = True,
    show_selectors: bool = True,
    show_examples: bool = True,
) -> List[str]:
    lines: List[str] = []
    filtered = list(entries)

    if heading:
        lines.append(heading)
        lines.append("")

    if include_table:
        if filtered:
            lines.extend(_render_group_table(filtered, show_policy=show_policy))
        else:
            lines.append("_No entries found._")
            lines.append("")

    for entry in filtered:
        lines.extend(
            _render_entry_details(
                entry,
                heading=None,
                show_policy=show_policy,
                show_flags=show_flags,
                show_selectors=show_selectors,
                show_examples=show_examples,
            )
        )

    return lines


def _render_path_templates(pathspecs: Sequence[PathSpec]) -> List[str]:
    if not pathspecs:
        return []

    lines: List[str] = []
    lines.append("**Filesystem Layout**")
    lines.append("| Id | Layout | Instantiation | Visibility | Description |")
    lines.append("| --- | --- | --- | --- | --- |")
    for spec in pathspecs:
        layout = "/".join(spec.layout_path)
        instantiation = "/".join(spec.instantiation_path)
        description = spec.description or "_None_"
        panel = spec.metadata.get("panel_id") if spec.metadata else spec.panel_id
        if panel:
            description = f"{description} (panel: `{panel}`)"
        lines.append(f"| `{spec.id}` | `{layout}` | `{instantiation}` | `{spec.visibility.value}` | {description} |")
    lines.append("")
    return lines


def _render_object(
    environment: Environment,
    entries: Sequence[ReferenceEntry],
    object_type: str,
    *,
    heading: Optional[str] = None,
    include_table: bool = True,
    show_policy: bool = True,
    show_flags: bool = True,
    show_selectors: bool = True,
    show_examples: bool = True,
    include_paths: bool = True,
) -> str:
    try:
        object_spec = environment.objects.get(object_type)
    except UnknownSpecError:
        raise ValueError(f"Object '{object_type}' not found in environment.")

    filtered = [
        entry for entry in entries if entry.object_type == object_type or entry.group == f"object:{object_type}"
    ]
    lines = _render_section_lines(
        filtered,
        heading=heading,
        include_table=include_table,
        show_policy=show_policy,
        show_flags=show_flags,
        show_selectors=show_selectors,
        show_examples=show_examples,
    )

    if include_paths:
        lines.extend(_render_path_templates(object_spec.pathspecs))

    return "\n".join(lines).rstrip() + "\n"


def _normalize_rule_ids(environment: Environment, rule_ids: Sequence[str]) -> Tuple[str, ...]:
    if not rule_ids:
        return tuple()
    normalized: List[str] = []
    existing_ids = {rule.id for rule in environment.rules.list()}
    for rule_id in rule_ids:
        if rule_id not in existing_ids:
            raise ValueError(f"Unknown rule id(s): {rule_id}")
        normalized.append(rule_id)
    return tuple(normalized)


def _collect_reference_entries(environment: Environment) -> List[ReferenceEntry]:
    entries: List[ReferenceEntry] = []

    for obj in environment.objects.list():
        group = f"object:{obj.type}"
        for function in obj.functions:
            entries.append(_build_object_entry(environment, group, obj, function))

    return entries


def _ensure_tuple(value: object) -> Tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    return (str(value),)


def _build_object_entry(
    environment: Environment,
    group: str,
    object_spec: ObjectSpec,
    function: ObjectFunctionSpec,
) -> ReferenceEntry:
    metadata: Mapping[str, object] = function.metadata or {}
    selectors_meta = metadata.get("selectors")
    selectors = (
        tuple(function.selectors)
        if getattr(function, "selectors", None)
        else tuple(selector for selector in selectors_meta or ())
    )
    if not selectors and "selectors" in metadata:
        selectors = _ensure_tuple(metadata["selectors"])
    flags: List[Tuple[str, str]] = []
    arguments_meta = metadata.get("arguments") or ()
    if arguments_meta:
        for argument in arguments_meta:
            if not isinstance(argument, Mapping):
                continue
            flag_tuple = tuple(argument.get("flags") or ())
            if not flag_tuple:
                continue
            flag_display = ", ".join(f"`{flag}`" for flag in flag_tuple)
            description_parts: List[str] = []
            help_text = argument.get("help")
            if help_text:
                description_parts.append(str(help_text))
            if argument.get("required"):
                description_parts.append("[required]")
            default_value = argument.get("default")
            if default_value not in (None, ""):
                description_parts.append(f"(default: {default_value})")
            description = " ".join(description_parts).strip()
            flags.append((flag_display, description))

    flags_meta = metadata.get("flags") or ()
    if flags_meta:
        for item in flags_meta:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                flag, description = item[0], item[1]
                flags.append((str(flag), str(description)))
    if not flags:
        flags_attr = tuple(getattr(function, "flags", ()) or ())
        if flags_attr:
            flags = [(str(flag), str(description)) for flag, description in flags_attr]
    examples_meta = metadata.get("examples") or ()
    examples = tuple(function.examples or ()) or tuple(str(example) for example in examples_meta)
    hooks = _ensure_tuple(metadata.get("hooks"))

    summary = function.description or metadata.get("summary") or f"{function.name} function for {object_spec.type}"
    policy = str(metadata.get("policy", "object"))
    rule_ids = _ensure_tuple(metadata.get("rule_ids"))
    rule_ids = _normalize_rule_ids(environment, rule_ids)

    return ReferenceEntry(
        group=group,
        name=function.name,
        summary=str(summary),
        selectors=selectors,
        flags=tuple(flags),
        examples=examples,
        policy=policy,
        object_type=object_spec.type,
        function=function.name,
        rule_ids=rule_ids,
        hooks=hooks,
    )


def _dedupe_entries(entries: Sequence[ReferenceEntry]) -> List[ReferenceEntry]:
    deduped: "OrderedDict[str, ReferenceEntry]" = OrderedDict()
    for entry in entries:
        key = entry.function or entry.name
        if key is None:
            deduped.setdefault(f"__unnamed__{id(entry)}", entry)
            continue
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = entry
            continue
        if existing.group.startswith("write") and not entry.group.startswith("write"):
            deduped[key] = entry
    return list(deduped.values())


def _strip_leading_heading(text: str) -> str:
    if not text:
        return text

    lines = text.splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public renderers
# ---------------------------------------------------------------------------


def render_rule_fragments(
    environment: Environment,
    *,
    rule_ids: Sequence[str] | None = None,
    object_types: Sequence[str] | None = None,
    function_refs: Sequence[tuple[str, str]] | None = None,
) -> str:
    """Render CLI-style fragments (rule/object/function) against the environment."""

    entries = _collect_reference_entries(environment)
    output_blocks: List[str] = []

    if object_types:
        for object_type in object_types:
            block = _render_object(environment, entries, object_type, heading=f"## {object_type}").strip()
            if block:
                output_blocks.append(block)

    seen_keys = set()

    if function_refs:
        for object_type, function_name in function_refs:
            entry = next(
                (entry for entry in entries if entry.object_type == object_type and entry.function == function_name),
                None,
            )
            if entry is None:
                raise ValueError(f"Unknown CLI function '{object_type}.{function_name}'.")
            key = entry.function or f"{entry.object_type}:{entry.name}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            output_blocks.append(render_function(entry).strip())

    if rule_ids:
        normalized_rules = _normalize_rule_ids(environment, rule_ids)
        for rule_id in normalized_rules:
            matching = [entry for entry in entries if rule_id in entry.rule_ids]
            if not matching:
                raise ValueError(f"Unknown rule id(s): {rule_id}")
            unique_matching = []
            for entry in _dedupe_entries(matching):
                key = entry.function or f"{entry.object_type}:{entry.name}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                unique_matching.append(entry)
            block = render_section(unique_matching, heading=f"## Rule {rule_id}").strip()
            if block:
                output_blocks.append(block)

    if not output_blocks:
        raise ValueError("No content selected. Provide rule, object, or function selectors.")

    return "\n\n".join(output_blocks).rstrip() + "\n"


def render_rules(environment: Environment, rule_ids: Iterable[str]) -> str:
    """Return full rule documents (frontmatter stripped) for provided ids."""

    lines: List[str] = []
    for rule_id in rule_ids:
        rule = _get_rule(environment, rule_id)
        if not rule:
            lines.append(f"_Rule `{rule_id}` not found in environment._")
            continue
        rule_content = _read_rule_body(rule)
        heading = f"## {rule.title or rule.id}"
        lines.append(heading)
        lines.append(rule_content.strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_function(entry: ReferenceEntry) -> str:
    """Render a single function entry."""

    lines = _render_entry_details(
        entry,
        heading=f"#### `{entry.name}`",
        show_policy=True,
        show_flags=True,
        show_selectors=True,
        show_examples=True,
    )
    return "\n".join(lines).rstrip() + "\n"


def render_section(
    entries: Sequence[ReferenceEntry],
    *,
    heading: Optional[str] = None,
    include_table: bool = True,
    show_policy: bool = True,
    show_flags: bool = True,
    show_selectors: bool = True,
    show_examples: bool = True,
) -> str:
    lines = _render_section_lines(
        entries,
        heading=heading,
        include_table=include_table,
        show_policy=show_policy,
        show_flags=show_flags,
        show_selectors=show_selectors,
        show_examples=show_examples,
    )
    return "\n".join(lines).rstrip() + "\n"


def render_agent_document(
    environment: Environment,
    agent_slug: str,
    *,
    identity: str | None = None,
    context: Mapping[str, str] | None = None,
    heading_level: int = 1,
) -> str:
    """Render the AGENT.md document for the given agent.

    Parameters
    ----------
    environment:
        The environment containing agent, role, rule, and object registries.
    agent_slug:
        Identifier of the agent to render.
    identity:
        Optional identity label (public key, UUID, etc.) to surface alongside the slug.
    context:
        Optional mapping of additional context metadata (process, thread, actor ids, etc.). Values are
        rendered in the order provided by the mapping.
    heading_level:
        Base heading level for the document heading. Sub-sections render at ``heading_level + 1`` (up
        to Markdown level 6).
    """

    agent = next((spec for spec in environment.agents.list() if spec.slug == agent_slug), None)
    if agent is None:
        raise ValueError(f"Agent '{agent_slug}' not registered in environment.")

    base_level = max(1, min(int(heading_level or 1), 6))
    heading_prefix = "#" * base_level
    section_prefix = "#" * min(base_level + 1, 6)

    lines: List[str] = []
    lines.append(f"{heading_prefix} Agent · {agent.title or agent.slug}")
    lines.append("")
    lines.append(f"**Agent slug:** `{agent.slug}`")
    if identity:
        lines.append(f"**Identity:** `{identity}`")
    if context:
        lines.append("")
        lines.append(f"{section_prefix} Context")
        for key, value in context.items():
            lines.append(f"- **{key}:** `{value}`")
    role_specs = [_get_role(environment, slug) for slug in agent.role_slugs]
    role_specs = [spec for spec in role_specs if spec is not None]
    if role_specs:
        lines.append("")
        lines.append(f"{section_prefix} Roles")
        lines.append("")
        lines.append(render_role_bundle(environment, tuple(spec.slug for spec in role_specs)).strip())
    else:
        lines.append("")
        lines.append("_Agent has no roles defined._")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_role_bundle(environment: Environment, role_slugs: Iterable[str]) -> str:
    """Render markdown describing the supplied role slugs."""

    lines: List[str] = []
    for index, slug in enumerate(role_slugs, start=1):
        role = _get_role(environment, slug)
        if role is None:
            lines.append(f"_Role `{slug}` not found._")
            continue
        heading = f"### Role {index}: {role.title or role.slug} (`{role.slug}`)"
        lines.append(heading)
        if role.description:
            lines.append(role.description)
        if role.policy_ids:
            policy_text = ", ".join(f"`{policy}`" for policy in role.policy_ids)
            lines.append(f"**Policies:** {policy_text}")
            fragments: List[str] = []
            for policy in role.policy_ids:
                try:
                    fragment = render_rule_fragments(environment, rule_ids=(policy,)).strip()
                except ValueError as exc:
                    fragments.append(f"_Unable to render policy `{policy}` fragments: {exc}_")
                else:
                    if fragment:
                        fragments.append(fragment)
            if fragments:
                lines.append("")
                lines.append("\n\n".join(fragments).strip())
        if role.protocol_ids:
            lines.append("")
            lines.append("**Protocols:**")
            for protocol_id in role.protocol_ids:
                protocol = _get_protocol(environment, protocol_id)
                if protocol is None:
                    lines.append(f"- `{protocol_id}` — _Protocol not found._")
                    continue
                summary = protocol.summary or "_No summary provided._"
                relative_path = _relative_path(Path(protocol.path), Path.cwd())
                display_name = protocol.title or protocol.slug
                lines.append(f"- [{display_name}]({relative_path}) — {summary}")
    lines.append("")
    return "\n".join(lines).strip() + "\n"

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _get_rule(environment: Environment, rule_id: str) -> RuleSpec | None:
    try:
        return environment.rules.get(rule_id)
    except Exception:
        return None


def _get_role(environment: Environment, role_slug: str) -> RoleSpec | None:
    try:
        return environment.roles.get(role_slug)
    except Exception:
        return None


def _get_protocol(environment: Environment, protocol_slug: str) -> ProtocolSpec | None:
    try:
        return environment.protocols.get(protocol_slug)
    except Exception:
        return None


def _relative_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _read_rule_body(rule: RuleSpec) -> str:
    path = Path(rule.path)
    if not path.exists():
        return f"_Rule content not found for `{rule.id}`._"
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_PATTERN.match(text)
    if match:
        return text[match.end() :]
    return text


__all__ = [
    "ReferenceEntry",
    "render_rule_fragments",
    "render_rules",
    "render_function",
    "render_section",
    "render_agent_document",
    "render_role_bundle",
    "render_constitution_summary",
    "render_environment_guide",
]
