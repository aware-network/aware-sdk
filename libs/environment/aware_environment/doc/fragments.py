"""Fragment rendering and application for rule templates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, TypedDict

from ..environment import Environment
from ..renderer import render_rule_fragments
from .markers import BEGIN_MARKER, END_MARKER, format_begin_marker, parse_begin_marker

Checksum = str
_CHECKSUM_LENGTH = 12


class FragmentAttributes(TypedDict, total=False):
    rule: str
    object: str
    function: str
    role: str
    checksum: str


def _normalize_attributes(attributes: Mapping[str, str]) -> FragmentAttributes:
    return FragmentAttributes({key: value for key, value in attributes.items() if key != "checksum"})


def _attribute_identity(attributes: Mapping[str, str]) -> Tuple[Tuple[str, str], ...]:
    return tuple(sorted((key, value) for key, value in attributes.items() if key != "checksum"))


def _compute_checksum(body: str) -> Checksum:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:_CHECKSUM_LENGTH]


@dataclass(frozen=True)
class RenderedFragment:
    attributes: FragmentAttributes
    body: str
    checksum: Checksum

    def identity(self) -> Tuple[Tuple[str, str], ...]:
        return _attribute_identity(self.attributes)


class FragmentApplyStatus(str, Enum):
    APPLIED = "applied"
    NO_CHANGE = "no_change"
    MISSING_MARKER = "missing_marker"
    CONFLICT = "conflict"


@dataclass
class FragmentApplyResult:
    attributes: FragmentAttributes
    status: FragmentApplyStatus
    detail: Optional[str] = None
    bytes_changed: int = 0


@dataclass
class DocsApplyReceipt:
    status: str
    fragments: List[FragmentApplyResult] = field(default_factory=list)
    dry_run: bool = False
    path: Optional[str] = None

    def counts(self) -> Dict[str, int]:
        tally = {
            FragmentApplyStatus.APPLIED.value: 0,
            FragmentApplyStatus.NO_CHANGE.value: 0,
            FragmentApplyStatus.MISSING_MARKER.value: 0,
            FragmentApplyStatus.CONFLICT.value: 0,
        }
        for fragment in self.fragments:
            tally[fragment.status.value] += 1
        return tally

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "dry_run": self.dry_run,
            "path": self.path,
            "counts": self.counts(),
            "fragments": [
                {
                    "attributes": dict(result.attributes),
                    "status": result.status.value,
                    "detail": result.detail,
                    "bytes_changed": result.bytes_changed,
                }
                for result in self.fragments
            ],
        }


@dataclass(frozen=True)
class _MarkerSpan:
    start: int
    end: int
    block: str
    attributes: FragmentAttributes


def _scan_markers(source: str) -> List[_MarkerSpan]:
    spans: List[_MarkerSpan] = []
    position = 0
    length = len(source)
    while position < length:
        start = source.find(BEGIN_MARKER, position)
        if start == -1:
            break
        end = source.find(END_MARKER, start)
        if end == -1:
            break
        end += len(END_MARKER)
        block = source[start:end]
        newline_index = block.find("\n")
        if newline_index == -1:
            position = end
            continue
        begin_line = block[:newline_index]
        try:
            attributes = parse_begin_marker(begin_line)
        except ValueError:
            position = end
            continue
        spans.append(
            _MarkerSpan(
                start=start,
                end=end,
                block=block,
                attributes=_normalize_attributes(attributes),
            )
        )
        position = end
    return spans


def _render_fragment_block(
    environment: Environment,
    *,
    rule_ids: Sequence[str] | None = None,
    object_types: Sequence[str] | None = None,
    function_refs: Sequence[Tuple[str, str]] | None = None,
) -> str:
    return render_rule_fragments(
        environment,
        rule_ids=tuple(rule_ids or ()),
        object_types=tuple(object_types or ()),
        function_refs=tuple(function_refs or ()),
    )


def render_fragment_for_attributes(environment: Environment, attributes: Mapping[str, str]) -> RenderedFragment:
    attrs = _normalize_attributes(attributes)
    function_refs: Sequence[Tuple[str, str]] | None = None
    object_types: Sequence[str] | None = None
    rule_ids: Sequence[str] | None = None

    if "function" in attrs:
        value = attrs["function"]
        separator = ":" if ":" in value else "." if "." in value else None
        if not separator:
            raise ValueError(f"Unsupported function reference '{value}'. Expected object:function.")
        object_type, function_name = value.split(separator, 1)
        function_refs = [(object_type, function_name)]
    elif "object" in attrs:
        object_types = [attrs["object"]]
    elif "rule" in attrs:
        rule_ids = [attrs["rule"]]

    body = _render_fragment_block(
        environment,
        rule_ids=rule_ids,
        object_types=object_types,
        function_refs=function_refs,
    ).strip("\n")
    checksum = _compute_checksum(body)
    rendered_attrs = FragmentAttributes(dict(attrs))
    return RenderedFragment(attributes=rendered_attrs, body=body, checksum=checksum)


def render_fragments(
    environment: Environment,
    *,
    rule_ids: Sequence[str] | None = None,
    object_types: Sequence[str] | None = None,
    function_refs: Sequence[Tuple[str, str]] | None = None,
) -> List[RenderedFragment]:
    fragments: List[RenderedFragment] = []

    if function_refs:
        for object_type, function_name in function_refs:
            attributes: FragmentAttributes = {"function": f"{object_type}:{function_name}"}
            fragments.append(render_fragment_for_attributes(environment, attributes))

    if object_types:
        for object_type in object_types:
            attributes = FragmentAttributes({"object": object_type})
            fragments.append(render_fragment_for_attributes(environment, attributes))

    if rule_ids:
        for rule_id in rule_ids:
            attributes = FragmentAttributes({"rule": rule_id})
            fragments.append(render_fragment_for_attributes(environment, attributes))

    return fragments


def apply_fragments(
    source: str,
    *,
    fragments: Sequence[RenderedFragment] | None = None,
    environment: Environment | None = None,
) -> tuple[str, DocsApplyReceipt]:
    spans = _scan_markers(source)
    span_map = {_attribute_identity(span.attributes): span for span in spans}

    if fragments is None:
        if environment is None:
            raise ValueError("Applying fragments requires either explicit fragments or an environment.")
        fragments_to_apply = [render_fragment_for_attributes(environment, span.attributes) for span in spans]
    else:
        fragments_to_apply = list(fragments)

    replacements: List[Tuple[int, int, str]] = []
    results: List[FragmentApplyResult] = []

    for fragment in fragments_to_apply:
        key = fragment.identity()
        span = span_map.get(key)
        if span is None:
            results.append(
                FragmentApplyResult(
                    attributes=fragment.attributes,
                    status=FragmentApplyStatus.MISSING_MARKER,
                    detail="Marker not found in target document.",
                )
            )
            continue

        replacement_attributes = FragmentAttributes(dict(fragment.attributes))
        replacement_attributes["checksum"] = fragment.checksum
        replacement = f"{format_begin_marker(replacement_attributes)}\n{fragment.body}\n{END_MARKER}"

        if replacement == span.block:
            results.append(
                FragmentApplyResult(
                    attributes=fragment.attributes,
                    status=FragmentApplyStatus.NO_CHANGE,
                )
            )
        else:
            replacements.append((span.start, span.end, replacement))
            delta = len(replacement) - len(span.block)
            results.append(
                FragmentApplyResult(
                    attributes=fragment.attributes,
                    status=FragmentApplyStatus.APPLIED,
                    bytes_changed=delta,
                )
            )

    updated = source
    if replacements:
        replacements.sort(key=lambda item: item[0])
        segments: List[str] = []
        last_index = 0
        for start, end, replacement in replacements:
            segments.append(source[last_index:start])
            segments.append(replacement)
            last_index = end
        segments.append(source[last_index:])
        updated = "".join(segments)

    status = "no_change"
    if any(result.status == FragmentApplyStatus.APPLIED for result in results):
        status = "applied"
    if any(result.status == FragmentApplyStatus.MISSING_MARKER for result in results):
        status = "partial"

    receipt = DocsApplyReceipt(status=status, fragments=results)
    return updated, receipt


__all__ = [
    "FragmentAttributes",
    "RenderedFragment",
    "FragmentApplyStatus",
    "FragmentApplyResult",
    "DocsApplyReceipt",
    "render_fragments",
    "render_fragment_for_attributes",
    "apply_fragments",
]
