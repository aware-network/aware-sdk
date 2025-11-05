"""Helpers for enriching object specifications with metadata."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, List, Tuple

from aware_environment.object.spec import ObjectSpec
from aware_environment.pathspec import PathSpec, Visibility

DEFAULT_ROOT_KEY = "workspace_root"

_PATH_PREFIX_MAP: dict[tuple[str, ...], tuple[str, int]] = {
    ("docs", "runtime", "process"): ("runtime_root", 3),
    ("runtime", "process"): ("runtime_root", 2),
    ("docs", "identities"): ("identities_root", 2),
    ("identities",): ("identities_root", 1),
    ("docs", "projects"): ("projects_root", 2),
    ("projects",): ("projects_root", 1),
    ("docs", "rules"): ("rules_root", 2),
    ("rules",): ("rules_root", 1),
}

_ROOT_PLACEHOLDER_MAP = {
    "repository": "repository_root",
    "workspace": "workspace_root",
}


@dataclass(frozen=True)
class PathMetadata:
    key: str
    template: str
    description: str
    selectors: Tuple[str, ...]
    visibility: str
    kind: str | None = None
    panel_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "key": self.key,
            "template": self.template,
            "description": self.description,
            "selectors": self.selectors,
            "visibility": self.visibility,
        }
        if self.kind is not None:
            payload["kind"] = self.kind
        if self.panel_id is not None:
            payload["panel_id"] = self.panel_id
        return payload


def path_metadata_from_pathspecs(pathspecs: Iterable[PathSpec]) -> List[PathMetadata]:
    entries: List[PathMetadata] = []
    for spec in pathspecs or ():
        instantiation = list(spec.instantiation_path or [])
        root_key = None
        skip = 0
        for prefix, (candidate_root, length) in _PATH_PREFIX_MAP.items():
            if tuple(instantiation[:length]) == prefix:
                root_key = candidate_root
                skip = length
                break
        remainder = instantiation[skip:]
        template_parts: list[str] = []
        template_root = root_key or DEFAULT_ROOT_KEY
        template_parts.append(f"{{{template_root}}}")
        for segment in remainder:
            if segment.startswith("{") and segment.endswith("}"):
                placeholder = segment[1:-1]
                mapped = _ROOT_PLACEHOLDER_MAP.get(placeholder)
                if mapped:
                    template_parts.append(f"{{{mapped}}}")
                    continue
            template_parts.append(segment)
        template = "/".join(template_parts)
        selectors = spec.required_selectors() if hasattr(spec, "required_selectors") else ()
        entry = PathMetadata(
            key=str(spec.id),
            template=template,
            description=spec.description or "",
            selectors=tuple(selectors),
            visibility=spec.visibility.value if isinstance(spec.visibility, Visibility) else str(spec.visibility),
            kind=str(spec.metadata.get("kind")) if "kind" in spec.metadata else None,
            panel_id=str(spec.panel_id) if spec.panel_id is not None else None,
        )
        entries.append(entry)
    return entries


def serialise_path_metadata(entries: Iterable[PathMetadata]) -> list[dict[str, object]]:
    return [entry.to_dict() for entry in entries]


def ensure_paths_metadata(spec: ObjectSpec) -> ObjectSpec:
    if "paths" in (spec.metadata or {}):
        return spec
    path_entries = serialise_path_metadata(path_metadata_from_pathspecs(spec.pathspecs))
    if not path_entries:
        return spec
    metadata = dict(spec.metadata or {})
    metadata["paths"] = path_entries
    return replace(spec, metadata=metadata)


__all__ = ["PathMetadata", "path_metadata_from_pathspecs", "serialise_path_metadata", "ensure_paths_metadata"]
