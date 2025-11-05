"""Registry implementation for object specifications."""

from __future__ import annotations

from typing import Iterable, List

from ..exceptions import DuplicateSpecError, UnknownSpecError
from .spec import ObjectSpec


class ObjectRegistry:
    """Registry that stores object specifications."""

    def __init__(self) -> None:
        self._items: dict[str, ObjectSpec] = {}

    def register(self, spec: ObjectSpec) -> None:
        if spec.type in self._items:
            raise DuplicateSpecError(f"Object '{spec.type}' is already registered")
        self._items[spec.type] = spec

    def register_many(self, specs: Iterable[ObjectSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def get(self, object_type: str) -> ObjectSpec:
        try:
            return self._items[object_type]
        except KeyError as exc:
            raise UnknownSpecError(f"Object '{object_type}' not registered") from exc

    def list(self) -> List[ObjectSpec]:
        return list(self._items.values())

    def clear(self) -> None:
        self._items.clear()
