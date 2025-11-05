"""Dataclasses describing object specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Tuple, TYPE_CHECKING

Metadata = Mapping[str, object]
HandlerFactory = Callable[..., Any]
AdapterFactory = Callable[..., Any]

if TYPE_CHECKING:
    from aware_environment.pathspec import PathSpec


@dataclass(frozen=True)
class ObjectFunctionSpec:
    """Represents a callable function exposed by an object."""

    name: str
    handler_factory: Optional[HandlerFactory] = None
    description: str = ""
    selectors: Tuple[str, ...] = field(default_factory=tuple)
    flags: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    examples: Tuple[str, ...] = field(default_factory=tuple)
    metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectSpec:
    """Represents an environment object and its functions."""

    type: str
    description: str
    functions: Tuple[ObjectFunctionSpec, ...]
    adapter_factory: Optional[AdapterFactory] = None
    roots: Mapping[str, str] = field(default_factory=dict)
    pathspecs: Tuple["PathSpec", ...] = field(default_factory=tuple)
    metadata: Metadata = field(default_factory=dict)

    def function_names(self) -> Tuple[str, ...]:
        return tuple(func.name for func in self.functions)
