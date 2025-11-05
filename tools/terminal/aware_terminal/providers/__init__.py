"""Provider integration helpers for aware-terminal."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Optional

from .base import (
    ProviderActionResult,
    ProviderContext,
    ProviderSessionResult,
    TerminalProvider,
    TerminalProviderInfo,
)
from .registry import ProviderRegistry, get_registry, registry


def _ensure_provider_package() -> None:
    """Attempt to import optional provider bundle (libs/providers/terminal)."""

    try:
        import aware_terminal_providers  # noqa: F401

        return
    except ModuleNotFoundError:
        pass

    repo_root = Path(__file__).resolve().parents[4]
    candidate = repo_root / "libs" / "providers" / "terminal"
    candidate_str = str(candidate)
    if candidate.exists() and candidate_str not in sys.path:
        sys.path.append(candidate_str)
        try:
            import aware_terminal_providers  # noqa: F401
        except ModuleNotFoundError:
            return


def list_providers() -> Iterable[TerminalProviderInfo]:
    _ensure_provider_package()
    return [provider.info for provider in registry.list()]


def get_provider(slug: str) -> Optional[TerminalProvider]:
    _ensure_provider_package()
    return registry.get(slug)


def run_provider_action(slug: str, action: str, **kwargs) -> Optional[ProviderActionResult | ProviderSessionResult]:
    _ensure_provider_package()
    provider = registry.get(slug)
    if provider is None:
        return None
    handler = getattr(provider, action, None)
    if handler is None:
        raise AttributeError(f"Provider '{slug}' has no action '{action}'")
    return handler(**kwargs)


__all__ = [
    "ProviderActionResult",
    "ProviderRegistry",
    "ProviderContext",
    "ProviderSessionResult",
    "TerminalProvider",
    "TerminalProviderInfo",
    "get_registry",
    "registry",
    "list_providers",
    "get_provider",
    "run_provider_action",
]

sys.modules.setdefault("aware_terminal.providers", sys.modules[__name__])
