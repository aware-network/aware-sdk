"""Kernel handlers for rule metadata and fragments."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from aware_environment.renderer import render_rule_fragments
from aware_environment.rule.spec import RuleSpec

from ...rules import RULES


def _rule_to_payload(spec: RuleSpec) -> dict:
    return {
        "id": spec.id,
        "title": spec.title,
        "summary": spec.summary,
        "layer": spec.layer,
        "version": spec.version,
        "path": str(spec.path),
        "metadata": dict(spec.metadata or {}),
    }


def list_rules(
    rules_root: Path | None = None,
    *,
    refresh: bool = False,
) -> List[dict]:
    """Return rule metadata."""

    # Parameters retained for compatibility; kernel rules are static.
    _ = (rules_root, refresh)
    return [_rule_to_payload(spec) for spec in RULES]


def _parse_function_refs(values: Iterable[str]) -> Tuple[Tuple[str, str], ...]:
    refs: List[Tuple[str, str]] = []
    for value in values:
        if not value:
            continue
        separator = ":" if ":" in value else "." if "." in value else None
        if not separator:
            raise ValueError(f"Function reference '{value}' must be object:function or object.function format.")
        object_type, function_name = value.split(separator, 1)
        if not object_type or not function_name:
            raise ValueError(f"Function reference '{value}' is invalid.")
        refs.append((object_type, function_name))
    return tuple(refs)


def fragments(
    rule: str | None = None,
    *,
    rule_ids: Sequence[str] | None = None,
    object_types: Sequence[str] | None = None,
    function_refs: Sequence[str] | None = None,
) -> dict:
    """Render rule fragments for the requested selectors."""

    selected_rules = []
    if rule:
        selected_rules.append(rule)
    selected_rules.extend(rule_ids or ())

    object_types_tuple = tuple(object_types or ())
    function_refs_tuple = _parse_function_refs(function_refs or ())

    if not selected_rules and not object_types_tuple and not function_refs_tuple:
        raise ValueError("Provide at least one selector (--rule, --object, or --function).")

    from ...registry import get_environment  # local import to avoid circular dependency

    environment = get_environment()

    markdown = render_rule_fragments(
        environment,
        rule_ids=tuple(selected_rules) if selected_rules else None,
        object_types=object_types_tuple or None,
        function_refs=function_refs_tuple or None,
    ).strip()

    return {
        "markdown": markdown,
        "rules": list(selected_rules),
        "objects": list(object_types_tuple),
        "functions": [":".join(ref) for ref in function_refs_tuple],
    }


__all__ = ["list_rules", "fragments"]
