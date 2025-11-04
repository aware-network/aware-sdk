"""Manifest loading helpers for aware-test-runner."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

DEFAULT_MANIFEST_ID = "internal"
MANIFEST_ENV = "AWARE_TEST_RUNNER_MANIFEST"
MANIFEST_FILE_ENV = "AWARE_TEST_RUNNER_MANIFEST_FILE"
MANIFEST_DIRS_ENV = "AWARE_TEST_RUNNER_MANIFEST_DIRS"


@dataclass
class ManifestData:
    """Normalized manifest data providing stable selectors and runtime suites."""

    identifier: str
    stable_entries: List[object]
    runtime_entries: List[Dict]


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

    for candidate in _default_manifest_candidates():
        try:
            return _resolve_manifest_by_id(candidate, visited=set())
        except FileNotFoundError:
            continue

    attempted = ", ".join(_default_manifest_candidates())
    raise FileNotFoundError(f"Unable to locate a default manifest (tried: {attempted})")


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

    # Fallback to package data
    data_pkg = resources.files("aware_test_runner.data.manifests")
    pkg_candidate_dir = data_pkg / manifest_id
    if pkg_candidate_dir.is_dir():
        payload = _load_manifest_directory(pkg_candidate_dir)
        return _normalize_manifest(manifest_id, payload, visited=visited)
    pkg_candidate_file = data_pkg / f"{manifest_id}.json"
    if pkg_candidate_file.is_file():
        payload = json.loads(pkg_candidate_file.read_text(encoding="utf-8"))
        return _normalize_manifest(manifest_id, payload, visited=visited)

    raise FileNotFoundError(f"Manifest '{manifest_id}' not found in manifest directories or package data.")


def _normalize_manifest(manifest_id: str, payload: Dict, *, visited: set[str]) -> ManifestData:
    extends = payload.get("extends")
    base = ManifestData(manifest_id, [], [])
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

    return ManifestData(manifest_id, stable_entries, runtime_entries)


def _iter_manifest_directories() -> Iterable[Path]:
    seen: set[Path] = set()

    dirs_env = os.environ.get(MANIFEST_DIRS_ENV)
    if dirs_env:
        for raw in dirs_env.split(os.pathsep):
            path = Path(raw.strip())
            if path.exists() and path not in seen:
                seen.add(path)
                yield path

    default = Path.cwd() / "configs" / "manifests"
    if default.exists() and default not in seen:
        seen.add(default)
        yield default

    package_root = Path(__file__).resolve().parents[2]
    repo_manifests = package_root / "configs" / "manifests"
    if repo_manifests.exists() and repo_manifests not in seen:
        seen.add(repo_manifests)
        yield repo_manifests


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


__all__ = ["ManifestData", "load_manifest", "DEFAULT_MANIFEST_ID"]
def _default_manifest_candidates() -> List[str]:
    candidates: List[str] = []
    if DEFAULT_MANIFEST_ID:
        candidates.append(DEFAULT_MANIFEST_ID)
    if "oss" not in candidates:
        candidates.append("oss")
    return candidates
