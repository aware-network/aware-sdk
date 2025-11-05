"""Packaged sample assets for kernel tests and fixtures."""

from __future__ import annotations

import json
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Iterable


def _copy_tree(source: Traversable, destination: Path) -> None:
    """Recursively copy traversable resources into *destination*."""

    destination.mkdir(parents=True, exist_ok=True)
    for entry in source.iterdir():
        target = destination / entry.name
        if entry.is_dir():
            _copy_tree(entry, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with entry.open("rb") as src, target.open("wb") as dst:
                dst.write(src.read())


def copy_rule_samples(destination: Path) -> Path:
    """Copy rule Markdown samples into *destination* and return the realised path."""

    destination = Path(destination).expanduser().resolve()
    rules_pkg = resources.files(__package__) / "rules"
    _copy_tree(rules_pkg, destination)
    return destination


def copy_role_registry_sample(destination: Path, *, filename: str = "role_registry.json") -> Path:
    """Write the sample role registry into *destination/filename*."""

    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    role_registry_resource = resources.files(__package__) / "roles" / "role_registry.json"
    target = destination / filename
    with role_registry_resource.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def iter_rule_sample_paths() -> Iterable[Path]:
    """Yield pathlib paths for packaged rule samples (for metadata assertions)."""

    rules_pkg = resources.files(__package__) / "rules"
    for entry in rules_pkg.rglob("*.md"):
        yield Path(entry.name)


__all__ = ["copy_rule_samples", "copy_role_registry_sample", "iter_rule_sample_paths"]
