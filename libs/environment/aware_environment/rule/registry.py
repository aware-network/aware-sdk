"""Registry implementation for rule specifications."""

from __future__ import annotations

from typing import Iterable, List

from ..exceptions import DuplicateSpecError, UnknownSpecError
from .spec import RuleSpec


class RuleRegistry:
    """Registry that stores rule specifications."""

    def __init__(self) -> None:
        self._items: dict[str, RuleSpec] = {}

    def register(self, spec: RuleSpec) -> None:
        if spec.id in self._items:
            raise DuplicateSpecError(f"Rule '{spec.id}' is already registered")
        self._items[spec.id] = spec

    def register_many(self, specs: Iterable[RuleSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def get(self, rule_id: str) -> RuleSpec:
        try:
            return self._items[rule_id]
        except KeyError as exc:
            raise UnknownSpecError(f"Rule '{rule_id}' not registered") from exc

    def list(self) -> List[RuleSpec]:
        return list(self._items.values())

    def clear(self) -> None:
        self._items.clear()
