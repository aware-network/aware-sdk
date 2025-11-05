"""Registry implementation for role specifications."""

from __future__ import annotations

from typing import Iterable, List

from ..exceptions import DuplicateSpecError, UnknownSpecError
from .spec import RoleSpec


class RoleRegistry:
    """Registry that stores role specifications."""

    def __init__(self) -> None:
        self._items: dict[str, RoleSpec] = {}

    def register(self, spec: RoleSpec) -> None:
        if spec.slug in self._items:
            raise DuplicateSpecError(f"Role '{spec.slug}' is already registered")
        self._items[spec.slug] = spec

    def register_many(self, specs: Iterable[RoleSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def get(self, slug: str) -> RoleSpec:
        try:
            return self._items[slug]
        except KeyError as exc:
            raise UnknownSpecError(f"Role '{slug}' not registered") from exc

    def list(self) -> List[RoleSpec]:
        return list(self._items.values())

    def clear(self) -> None:
        self._items.clear()
