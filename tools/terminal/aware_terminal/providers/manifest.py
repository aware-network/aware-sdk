from __future__ import annotations

import os
import sys
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path
from typing import Optional


@lru_cache(maxsize=1)
def provider_manifests_root() -> Path:
    override = os.environ.get("AWARE_TERMINAL_MANIFEST_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    # Development override takes precedence
    dev_root = os.environ.get("AWARE_TERMINAL_DEV_ROOT")
    if dev_root:
        candidate = Path(dev_root).expanduser().resolve()
        package_dir = candidate / "libs" / "providers" / "terminal" / "aware_terminal_providers"
        if package_dir.exists():
            if str(package_dir.parent) not in sys.path:
                sys.path.append(str(package_dir.parent))
            manifests = package_dir / "providers"
            if manifests.exists():
                return manifests

    spec = find_spec("aware_terminal_providers")
    if spec and spec.origin:
        package_path = Path(spec.origin).resolve().parent
        return package_path / "providers"

    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "libs" / "providers" / "terminal"
        if candidate.exists():
            if str(candidate) not in sys.path:
                sys.path.append(str(candidate))
            spec = find_spec("aware_terminal_providers")
            if spec and spec.origin:
                return Path(spec.origin).resolve().parent / "providers"
            break

    raise RuntimeError("aware_terminal_providers package not found; manifests unavailable")


@lru_cache(maxsize=1)
def provider_update_script() -> Optional[Path]:
    override = os.environ.get("AWARE_TERMINAL_MANIFEST_UPDATE_SCRIPT")
    if override:
        script = Path(override).expanduser().resolve()
        return script if script.exists() else None

    # Detect repo root when running from source
    roots = []
    dev_root = os.environ.get("AWARE_TERMINAL_DEV_ROOT")
    if dev_root:
        roots.append(Path(dev_root).expanduser().resolve())
    up = Path(__file__).resolve()
    roots.extend(up.parents)
    for root in roots:
        script = root / "libs" / "providers" / "terminal" / "scripts" / "update_provider_versions.py"
        if script.exists():
            return script
    return None


def manifests_available() -> bool:
    try:
        root = provider_manifests_root()
    except RuntimeError:
        return False
    return root.exists()
