"""Registry implementation for agent specifications."""

from __future__ import annotations

from typing import Iterable, List

from ..exceptions import DuplicateSpecError, UnknownSpecError
from .spec import AgentSpec


class AgentRegistry:
    """Registry that stores agent specifications."""

    def __init__(self) -> None:
        self._items: dict[str, AgentSpec] = {}

    def register(self, spec: AgentSpec) -> None:
        if spec.slug in self._items:
            raise DuplicateSpecError(f"Agent '{spec.slug}' is already registered")
        self._items[spec.slug] = spec

    def register_many(self, specs: Iterable[AgentSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def get(self, slug: str) -> AgentSpec:
        try:
            return self._items[slug]
        except KeyError as exc:
            raise UnknownSpecError(f"Agent '{slug}' not registered") from exc

    def list(self) -> List[AgentSpec]:
        return list(self._items.values())

    def clear(self) -> None:
        self._items.clear()
