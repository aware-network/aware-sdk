"""Argument specification helpers for environment objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class ArgumentSpec:
    """Describe a CLI argument exposed by an object function."""

    name: str
    flags: Sequence[str]
    help: str = ""
    required: bool = False
    multiple: bool = False
    expects_value: bool = True
    default: object | None = None
    value_type: object | None = None
    choices: Sequence[str] | None = None

    def to_metadata(self) -> dict[str, object | None]:
        return {
            "name": self.name,
            "flags": tuple(self.flags),
            "help": self.help,
            "required": self.required,
            "multiple": self.multiple,
            "expects_value": self.expects_value,
            "default": self.default,
            "type": self.value_type,
            "choices": tuple(self.choices) if self.choices is not None else None,
        }


def serialize_arguments(arguments: Iterable[ArgumentSpec]) -> Tuple[dict[str, object | None], ...]:
    """Convert an iterable of ArgumentSpec instances into stable metadata tuples."""

    return tuple(argument.to_metadata() for argument in arguments)


def serialize_argument_map(argument_map: Mapping[str, Sequence[ArgumentSpec]]) -> dict[str, Tuple[dict[str, object | None], ...]]:
    """Convert a mapping of function name -> ArgumentSpec sequence into metadata."""

    return {name: serialize_arguments(specs) for name, specs in argument_map.items()}


ArgumentDescriptor = ArgumentSpec  # backwards compatibility for existing specs


__all__ = ["ArgumentSpec", "ArgumentDescriptor", "serialize_arguments", "serialize_argument_map"]
