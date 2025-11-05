"""Helpers for reading and writing terminal descriptors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from .._shared.fs_utils import write_json_atomic
from .models import TerminalDescriptorModel


def terminals_dir(aware_root: Path, thread_identifier: str) -> Path:
    """Return the directory that stores terminal descriptors for a thread."""
    return Path(aware_root).expanduser().resolve() / "threads" / thread_identifier / "terminals"


def descriptor_path(aware_root: Path, thread_identifier: str, terminal_id: str) -> Path:
    """Return the path to a terminal descriptor JSON file."""
    return terminals_dir(aware_root, thread_identifier) / f"{terminal_id}.json"


def load_descriptor(path: Path) -> Optional[TerminalDescriptorModel]:
    """Load a descriptor document as a typed descriptor model."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    try:
        return TerminalDescriptorModel.model_validate(data)
    except Exception:
        return None


def write_descriptor(path: Path, descriptor: Union[TerminalDescriptorModel, Dict[str, Any]]) -> TerminalDescriptorModel:
    """Persist a descriptor to disk returning the typed model."""
    if isinstance(descriptor, TerminalDescriptorModel):
        payload = descriptor.model_dump(mode="json")
        model = descriptor
    else:
        payload = descriptor
        model = TerminalDescriptorModel.model_validate(payload)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, payload)
    return model


def delete_descriptor(path: Path) -> None:
    """Remove a descriptor file if it exists."""
    try:
        Path(path).unlink()
    except FileNotFoundError:
        return


def list_descriptors(directory: Path) -> List[Dict[str, Any]]:
    """Return all descriptors under a directory as dictionaries."""
    directory = Path(directory)
    if not directory.exists():
        return []

    descriptors: List[Dict[str, Any]] = []
    for candidate in sorted(directory.glob("*.json")):
        descriptor = load_descriptor(candidate)
        if descriptor:
            descriptors.append(descriptor)
    return descriptors


def normalise_env(values: Optional[Iterable[str]]) -> Dict[str, str]:
    """Convert KEY=VALUE strings into a dict; invalid items raise ValueError."""
    env_map: Dict[str, str] = {}
    if not values:
        return env_map
    for item in values:
        if "=" not in item:
            raise ValueError(f"Environment value '{item}' must be KEY=VALUE.")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Environment value '{item}' missing key.")
        env_map[key] = value
    return env_map


__all__ = [
    "terminals_dir",
    "descriptor_path",
    "load_descriptor",
    "write_descriptor",
    "delete_descriptor",
    "list_descriptors",
    "normalise_env",
]
