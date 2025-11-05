"""aware-terminal provider registry bridge package."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_terminal_package() -> None:
    try:
        import aware_terminal  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    root = Path(__file__).resolve()
    for _ in range(5):
        root = root.parent
    candidate = root / "tools" / "terminal"
    candidate_str = str(candidate)
    if candidate.exists() and candidate_str not in sys.path:
        sys.path.append(candidate_str)

    try:
        import aware_terminal  # noqa: F401
    except ModuleNotFoundError as exc:
        raise RuntimeError("aware_terminal package is required for aware_terminal_providers.") from exc


_ensure_terminal_package()

from aware_terminal.providers import (  # noqa: E402
    ProviderActionResult,
    ProviderRegistry,
    ProviderSessionResult,
    TerminalProvider,
    TerminalProviderInfo,
    get_registry,
    registry,
)

from . import providers as _providers  # noqa: F401,E402

__all__ = [
    "ProviderActionResult",
    "ProviderSessionResult",
    "TerminalProvider",
    "TerminalProviderInfo",
    "ProviderRegistry",
    "registry",
    "get_registry",
]
