"""Registry implementation for protocol specifications."""

from __future__ import annotations

from typing import Iterable, List

from ..exceptions import DuplicateSpecError, UnknownSpecError
from .spec import ProtocolSpec


class ProtocolRegistry:
    """Registry that stores protocol specifications."""

    def __init__(self) -> None:
        self._items: dict[str, ProtocolSpec] = {}

    def register(self, spec: ProtocolSpec) -> None:
        if spec.slug in self._items:
            raise DuplicateSpecError(f"Protocol '{spec.slug}' is already registered")
        self._items[spec.slug] = spec

    def register_many(self, specs: Iterable[ProtocolSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def get(self, protocol_slug: str) -> ProtocolSpec:
        try:
            return self._items[protocol_slug]
        except KeyError as exc:
            raise UnknownSpecError(f"Protocol '{protocol_slug}' not registered") from exc

    def list(self) -> List[ProtocolSpec]:
        return list(self._items.values())

    def clear(self) -> None:
        self._items.clear()
