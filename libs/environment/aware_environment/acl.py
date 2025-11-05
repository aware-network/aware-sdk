"""Shared ACL request/response structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping, Sequence

from .environment import Environment
from .exceptions import PathSpecResolutionError, UnknownSpecError
from .object.spec import ObjectSpec
from .pathspec import PathSpec, resolve_pathspec


@dataclass(frozen=True)
class AccessRequest:
    agent_slug: str
    role_slug: str
    object_type: str
    function_name: str
    selectors: Mapping[str, str] = field(default_factory=dict)
    root: Path | None = None
    private_root: Path | None = None
    categories: Sequence[str] | None = None


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str = ""
    metadata: Mapping[str, object] | None = None
    apt_id: str | None = None


@dataclass(frozen=True)
class AccessSnapshot:
    agent_slug: str
    roles: Sequence[str]
    permissions: Mapping[str, Sequence[str]]


def evaluate_access(environment: Environment | None, request: AccessRequest) -> AccessDecision:
    """Resolve requested object/function against environment PathSpecs.

    Current implementation always allows access but returns the resolved
    filesystem paths grouped by category for downstream enforcement.
    """

    base_meta = {
        "paths": {},
        "role": request.role_slug,
        "object": request.object_type,
        "function": request.function_name,
    }

    if environment is None:
        return AccessDecision(allowed=True, metadata=base_meta, apt_id=request.agent_slug)

    try:
        object_spec = environment.objects.get(request.object_type)
    except UnknownSpecError:
        return AccessDecision(allowed=True, metadata=base_meta, apt_id=request.agent_slug)

    function_spec = _get_function_spec(object_spec, request.function_name)
    if function_spec is None:
        return AccessDecision(allowed=True, metadata=base_meta, apt_id=request.agent_slug)

    pathspecs_meta = function_spec.metadata.get("pathspecs") if function_spec.metadata else None
    if not isinstance(pathspecs_meta, Mapping):
        return AccessDecision(allowed=True, metadata=base_meta, apt_id=request.agent_slug)

    categories = list(request.categories) if request.categories else list(pathspecs_meta.keys())
    selectors = _build_selector_map(object_spec, request.selectors)
    resolved: Dict[str, list[str]] = {}
    root = request.root or Path(".")
    private_root = request.private_root or root

    for category in categories:
        source = pathspecs_meta.get(category)
        if source is None:
            continue
        ids = _collect_ids(source, selectors)
        for spec_id in dict.fromkeys(ids):
            spec = object_spec_pathspec(object_spec, spec_id)
            if spec is None:
                continue
            try:
                path = resolve_pathspec(spec, selectors=selectors, root=root, private_root=private_root)
            except PathSpecResolutionError:
                continue
            resolved.setdefault(category, []).append(str(path))

    meta = dict(base_meta)
    meta["paths"] = resolved
    return AccessDecision(allowed=True, metadata=meta, apt_id=request.agent_slug)


def object_spec_pathspec(object_spec: ObjectSpec, spec_id: str) -> PathSpec | None:
    for spec in object_spec.pathspecs:
        if spec.id == spec_id:
            return spec
    return None


def _get_function_spec(object_spec: ObjectSpec, name: str):
    for function in object_spec.functions:
        if function.name == name:
            return function
    return None


def _build_selector_map(object_spec: ObjectSpec, selectors: Mapping[str, str]) -> Dict[str, str]:
    combined: Dict[str, str] = {}
    metadata = object_spec.metadata or {}
    if isinstance(metadata, Mapping):
        defaults = metadata.get("default_selectors")
        if isinstance(defaults, Mapping):
            combined.update({str(key): str(value) for key, value in defaults.items()})
    combined.update({str(key): str(value) for key, value in selectors.items()})
    return combined


def _collect_ids(source: object, selectors: Mapping[str, str]) -> list[str]:
    if source is None:
        return []
    if isinstance(source, (list, tuple, set)):
        return [str(item) for item in source]
    if isinstance(source, str):
        return [source]
    if isinstance(source, Mapping):
        collected: list[str] = []
        if "all" in source:
            collected.extend(_collect_ids(source["all"], selectors))
        for key, value in source.items():
            if key == "all":
                continue
            selector_value = selectors.get(key)
            if selector_value is None:
                continue
            if isinstance(value, Mapping):
                matched = value.get(selector_value)
                collected.extend(_collect_ids(matched, selectors))
            else:
                collected.extend(_collect_ids(value, selectors))
        return collected
    return [str(source)]
