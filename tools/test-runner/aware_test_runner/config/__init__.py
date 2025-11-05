"""Manifest loading helpers for aware-test-runner."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

DEFAULT_MANIFEST_ID: Optional[str] = None
MANIFEST_ENV = "AWARE_TEST_RUNNER_MANIFEST"
MANIFEST_FILE_ENV = "AWARE_TEST_RUNNER_MANIFEST_FILE"
MANIFEST_DIRS_ENV = "AWARE_TEST_RUNNER_MANIFEST_DIRS"


@dataclass
class DiscoveryNameTemplate:
    """Formatting instructions for suite names derived from discovery rules."""

    strategy: Literal["path_join", "template", "metadata"] = "path_join"
    template: Optional[str] = None
    reverse: bool = False
    delimiter: str = "_"
    fallback: Optional[str] = None


@dataclass
class DiscoveryRule:
    """Definition for filesystem-driven suite discovery."""

    id: str
    category: str
    type: Literal["package"] = "package"
    root: str = "."
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    max_depth: Optional[int] = None
    tests_dir: str = "tests"
    require_metadata: bool = False
    metadata_field: Optional[str] = None
    include_root: bool = False
    name: DiscoveryNameTemplate = field(default_factory=DiscoveryNameTemplate)
    description: Optional[str] = None
    enabled: bool = True
    category_aliases: List[str] = field(default_factory=list)


@dataclass
class ManifestData:
    """Normalized manifest data providing stable selectors and runtime suites."""

    identifier: str
    stable_entries: List[object]
    runtime_entries: List[Dict]
    discovery_rules: List[DiscoveryRule]


def load_manifest(*, manifest_id: Optional[str] = None, manifest_file: Optional[str] = None) -> ManifestData:
    """Resolve the manifest to load, honoring CLI parameters and environment overrides."""
    file_override = manifest_file or os.environ.get(MANIFEST_FILE_ENV)
    if file_override:
        payload = _load_manifest_payload(Path(file_override))
        resolved_id = payload.get("id") or Path(file_override).stem
        return _normalize_manifest(resolved_id, payload, visited=set())

    id_override = manifest_id or os.environ.get(MANIFEST_ENV)
    if id_override:
        return _resolve_manifest_by_id(id_override, visited=set())

    attempted = []
    if DEFAULT_MANIFEST_ID:
        try:
            return _resolve_manifest_by_id(DEFAULT_MANIFEST_ID, visited=set())
        except FileNotFoundError:
            attempted.append(DEFAULT_MANIFEST_ID)

    raise FileNotFoundError(
        "No test manifest provided. Supply --manifest or --manifest-file, or set "
        "AWARE_TEST_RUNNER_MANIFEST / AWARE_TEST_RUNNER_MANIFEST_FILE."
    )


def _resolve_manifest_by_id(manifest_id: str, *, visited: set[str]) -> ManifestData:
    if manifest_id in visited:
        raise RuntimeError(f"Cyclic manifest inheritance detected: {' -> '.join(list(visited) + [manifest_id])}")
    visited.add(manifest_id)

    for directory in _iter_manifest_directories():
        candidate_dir = directory / manifest_id
        if candidate_dir.is_dir():
            payload = _load_manifest_directory(candidate_dir)
            return _normalize_manifest(manifest_id, payload, visited=visited)

        candidate_file = directory / f"{manifest_id}.json"
        if candidate_file.is_file():
            payload = _load_manifest_payload(candidate_file)
            return _normalize_manifest(manifest_id, payload, visited=visited)

    raise FileNotFoundError(f"Manifest '{manifest_id}' not found in configured manifest directories.")


def _normalize_manifest(manifest_id: str, payload: Dict, *, visited: set[str]) -> ManifestData:
    extends = payload.get("extends")
    base = ManifestData(manifest_id, [], [], _default_discovery_rules())
    if extends:
        if isinstance(extends, str):
            if extends.endswith(".json") or "/" in extends:
                base = _normalize_manifest(
                    manifest_id=f"{manifest_id}#base",
                    payload=_load_manifest_payload(Path(extends)),
                    visited=visited.copy(),
                )
            else:
                base = _resolve_manifest_by_id(extends, visited=visited.copy())

    stable_entries = _merge_entries(base.stable_entries, _extract_entries(payload, "stable"), _stable_entry_key)
    runtime_entries = _merge_entries(base.runtime_entries, _extract_entries(payload, "runtime"), _runtime_entry_key)
    discovery_rules = _merge_discovery_rules(base.discovery_rules, _extract_discovery_rules(payload))
    if not discovery_rules:
        discovery_rules = _default_discovery_rules()

    return ManifestData(manifest_id, stable_entries, runtime_entries, discovery_rules)


def _iter_manifest_directories() -> Iterable[Path]:
    seen: set[Path] = set()

    dirs_env = os.environ.get(MANIFEST_DIRS_ENV)
    if dirs_env:
        for raw in dirs_env.split(os.pathsep):
            path = Path(raw.strip())
            if path.exists() and path not in seen:
                seen.add(path)
                yield path

    cwd = Path.cwd().resolve()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / "configs" / "manifests"
        if candidate.exists() and candidate not in seen:
            seen.add(candidate)
            yield candidate

    for parent in [cwd, *cwd.parents]:
        candidate = parent / "aware_sdk" / "configs" / "manifests"
        if candidate.exists() and candidate not in seen:
            seen.add(candidate)
            yield candidate

    for parent in [cwd, *cwd.parents]:
        candidate = parent / "apps" / "aware-sdk" / "aware_sdk" / "configs" / "manifests"
        if candidate.exists() and candidate not in seen:
            seen.add(candidate)
            yield candidate


def _load_manifest_payload(source: Path) -> Dict:
    if source.is_dir():
        return _load_manifest_directory(source)

    if not source.is_file():
        raise FileNotFoundError(f"Manifest file '{source}' does not exist.")

    with source.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Manifest file '{source}' must contain a JSON object.")
        return data


def _load_manifest_directory(directory: Path) -> Dict:
    payload: Dict[str, object] = {}

    manifest_meta = directory / "manifest.json"
    if manifest_meta.is_file():
        with manifest_meta.open("r", encoding="utf-8") as handle:
            meta = json.load(handle)
            if isinstance(meta, dict):
                payload.update(meta)

    payload["stable"] = _read_manifest_section(directory / "stable.json")
    payload["runtime"] = _read_manifest_section(directory / "runtime.json")
    payload.setdefault("id", directory.name)
    return payload


def _read_manifest_section(path: Path) -> List:
    if not path.is_file():
        return []

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, dict):
        suites = data.get("suites")
        if isinstance(suites, list):
            return suites
        return []

    if isinstance(data, list):
        return data

    return []


def _extract_entries(payload: Dict, key: str) -> List:
    # Accept multiple key spellings for compatibility.
    candidates: Sequence[str] = (
        key,
        f"{key}_suites",
        "suites" if key == "runtime" else "",
    )
    for candidate in candidates:
        if candidate and candidate in payload:
            value = payload.get(candidate)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                suites = value.get("suites")
                if isinstance(suites, list):
                    return suites
    return []


def _extract_discovery_rules(payload: Dict) -> List[DiscoveryRule]:
    rules_value = payload.get("discovery")
    if not isinstance(rules_value, list):
        return []

    parsed: List[DiscoveryRule] = []
    for entry in rules_value:
        if not isinstance(entry, dict):
            raise ValueError(f"Discovery rule entries must be objects, got {type(entry).__name__!r}")
        parsed.append(_parse_discovery_rule(entry))
    return parsed


def _parse_discovery_rule(data: Dict[str, Any]) -> DiscoveryRule:
    if "id" not in data or "category" not in data:
        raise ValueError("Discovery rules must include 'id' and 'category' fields.")

    rule_id = str(data["id"])
    category = str(data["category"])
    rule_type = str(data.get("type", "package"))
    if rule_type not in {"package"}:
        raise ValueError(f"Unsupported discovery rule type '{rule_type}' for rule '{rule_id}'.")

    root = str(data.get("root", "."))
    include = [str(item) for item in data.get("include", []) if isinstance(item, str)]
    exclude = [str(item) for item in data.get("exclude", []) if isinstance(item, str)]

    max_depth_value = data.get("max_depth")
    max_depth: Optional[int]
    if max_depth_value is None:
        max_depth = None
    else:
        if isinstance(max_depth_value, int):
            max_depth = max_depth_value
        elif isinstance(max_depth_value, (float, str)) and str(max_depth_value).isdigit():
            max_depth = int(max_depth_value)
        else:
            raise ValueError(f"Discovery rule '{rule_id}' has invalid max_depth value: {max_depth_value!r}")

    tests_dir = str(data.get("tests_dir", "tests"))
    require_metadata = bool(data.get("require_metadata", False))
    metadata_field = data.get("metadata_field")
    if metadata_field is not None:
        metadata_field = str(metadata_field)
    include_root = bool(data.get("include_root", False))
    enabled = bool(data.get("enabled", True))

    name_block = data.get("name", {}) or {}
    if not isinstance(name_block, dict):
        raise ValueError(f"Discovery rule '{rule_id}' has invalid 'name' configuration.")
    strategy = str(name_block.get("strategy", "path_join"))
    if strategy not in {"path_join", "template", "metadata"}:
        raise ValueError(
            f"Discovery rule '{rule_id}' has unsupported name strategy '{strategy}'. "
            "Supported strategies: path_join, template, metadata."
        )
    name_template = DiscoveryNameTemplate(
        strategy=strategy,  # type: ignore[arg-type]
        template=name_block.get("template"),
        reverse=bool(name_block.get("reverse", False)),
        delimiter=str(name_block.get("delimiter", "_")),
        fallback=name_block.get("fallback"),
    )

    description = data.get("description")
    if description is not None:
        description = str(description)

    category_aliases = [str(item) for item in data.get("category_aliases", []) if isinstance(item, str)]

    return DiscoveryRule(
        id=rule_id,
        category=category,
        type="package",
        root=root,
        include=include,
        exclude=exclude,
        max_depth=max_depth,
        tests_dir=tests_dir,
        require_metadata=require_metadata,
        metadata_field=metadata_field,
        include_root=include_root,
        name=name_template,
        description=description,
        enabled=enabled,
        category_aliases=category_aliases,
    )


def _merge_discovery_rules(base: List[DiscoveryRule], overlay: List[DiscoveryRule]) -> List[DiscoveryRule]:
    merged: Dict[str, DiscoveryRule] = {rule.id: rule for rule in base}
    order: List[str] = [rule.id for rule in base]

    for rule in overlay:
        if not rule.enabled:
            if rule.id in merged:
                del merged[rule.id]
            continue
        merged[rule.id] = rule
        if rule.id not in order:
            order.append(rule.id)

    return [merged[rule_id] for rule_id in order if rule_id in merged]


DEFAULT_DISCOVERY_RULES_DATA: List[Dict[str, Any]] = [
    {
        "id": "grammar",
        "category": "grammar",
        "type": "package",
        "root": "languages",
        "max_depth": 1,
        "tests_dir": "grammar/grammar/tests",
        "name": {
            "strategy": "template",
            "template": "{name}-grammar",
        },
        "description": "{name_title} grammar tests",
    },
    {
        "id": "libraries",
        "category": "lib",
        "category_aliases": ["libs"],
        "type": "package",
        "root": "libs",
        "max_depth": 2,
        "tests_dir": "tests",
        "name": {
            "strategy": "path_join",
            "reverse": True,
            "delimiter": "_",
        },
        "description": "{path_title} library tests",
    },
    {
        "id": "domains",
        "category": "domains",
        "type": "package",
        "root": "languages/python/domains",
        "max_depth": 1,
        "tests_dir": "tests",
        "name": {
            "strategy": "path_join",
            "delimiter": "_",
        },
        "description": "{name_title} domain tests",
    },
    {
        "id": "tools",
        "category": "tools",
        "type": "package",
        "root": "tools",
        "max_depth": 1,
        "tests_dir": "tests",
        "name": {
            "strategy": "template",
            "template": "{name_dash}",
        },
        "description": "{name} tooling tests",
    },
]


def _default_discovery_rules() -> List[DiscoveryRule]:
    return [_parse_discovery_rule(rule_data) for rule_data in DEFAULT_DISCOVERY_RULES_DATA]


def _merge_entries(base: List, overlay: List, key_func) -> List:
    merged: Dict[Optional[str], object] = {}

    def _coerce(entry) -> object:
        return entry

    for entry in base:
        merged[key_func(entry)] = _coerce(entry)

    for entry in overlay:
        key = key_func(entry)
        merged[key] = _coerce(entry)

    # Preserve insertion order: base keys first, then overlay keys that were new.
    ordered: List = []
    seen: set = set()
    for entry in base + overlay:
        key = key_func(entry)
        if key in seen:
            continue
        seen.add(key)
        if key in merged:
            ordered.append(merged[key])
    return ordered


def _stable_entry_key(entry) -> Optional[str]:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        name = entry.get("name")
        if isinstance(name, str):
            return name
    return None


def _runtime_entry_key(entry) -> Optional[str]:
    if isinstance(entry, dict):
        name = entry.get("name")
        if isinstance(name, str):
            return name
    return None


__all__ = ["ManifestData", "DiscoveryRule", "DiscoveryNameTemplate", "load_manifest", "DEFAULT_MANIFEST_ID"]
