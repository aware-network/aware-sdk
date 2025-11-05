"""Provider registry primitives for aware-terminal."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from .base import TerminalProvider


class ProviderRegistry:
    """In-memory registry storing available terminal providers."""

    def __init__(self) -> None:
        self._providers: Dict[str, TerminalProvider] = {}

    def register(self, provider: TerminalProvider, *, replace: bool = False) -> None:
        slug = provider.info.slug
        if not replace and slug in self._providers:
            raise ValueError(f"Provider '{slug}' already registered")
        self._providers[slug] = provider

    def get(self, slug: str) -> Optional[TerminalProvider]:
        return self._providers.get(slug)

    def list(self) -> Iterable[TerminalProvider]:
        return tuple(self._providers.values())

    def remove(self, slug: str) -> Optional[TerminalProvider]:
        return self._providers.pop(slug, None)


_REGISTRY = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    return _REGISTRY


registry = get_registry()
