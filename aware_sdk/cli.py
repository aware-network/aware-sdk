"""Entry points for the aware-sdk helper CLI."""

from __future__ import annotations

import json
import sys
from importlib.metadata import version

from . import __version__


def info() -> int:
    """Emit basic package information (versions of bundled dependencies)."""
    payload = {
        "aware_sdk": __version__,
        "aware_release": _safe_version("aware-release"),
        "aware_test_runner": _safe_version("aware-test-runner"),
        "aware_file_system": _safe_version("aware-file-system"),
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    """CLI entry point."""
    return info()


def _safe_version(dist: str) -> str:
    try:
        return version(dist)
    except Exception:
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
