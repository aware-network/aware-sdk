"""PathSpec definitions for environment object materialisation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence, Tuple

from .exceptions import PathSpecResolutionError

_PLACEHOLDER_PATTERN = re.compile(r"{([^{}]+)}")


class Visibility(Enum):
    """Controls whether seeded content is public or private."""

    PUBLIC = "public"
    PRIVATE = "private"


@dataclass(frozen=True)
class PathSpec:
    """Describes how an object materialises on disk."""

    id: str
    layout_path: Tuple[str, ...]
    instantiation_path: Tuple[str, ...]
    visibility: Visibility = Visibility.PUBLIC
    panel_id: str | None = None
    description: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def layout(
        self,
        selectors: Mapping[str, str] | None = None,
    ) -> Path:
        """Return the logical layout path with placeholders resolved."""

        resolved = _resolve_segments(self.layout_path, selectors or {})
        return Path(*resolved)

    def instantiate(
        self,
        root: Path,
        *,
        selectors: Mapping[str, str] | None = None,
        private_root: Path | None = None,
    ) -> Path:
        """Return the instantiation path joined to the provided root."""

        base = root if self.visibility is Visibility.PUBLIC else private_root or root
        resolved = _resolve_segments(self.instantiation_path, selectors or {})
        return base.joinpath(*resolved)

    def declared_selectors(self) -> Tuple[str, ...]:
        """Selectors explicitly declared via metadata."""

        raw = self.metadata.get("selectors")
        if raw is None:
            return tuple()
        if isinstance(raw, str):
            return (raw,)
        if isinstance(raw, Sequence):
            return tuple(str(item) for item in raw)
        return (str(raw),)

    def inferred_selectors(self) -> Tuple[str, ...]:
        """Selectors inferred from placeholders in layout/instantiation paths."""

        names = set()
        for segment in (*self.layout_path, *self.instantiation_path):
            names.update(_PLACEHOLDER_PATTERN.findall(segment))
        return tuple(sorted(names))

    def required_selectors(self) -> Tuple[str, ...]:
        """Union of declared + inferred selectors."""

        declared = set(self.declared_selectors())
        declared.update(self.inferred_selectors())
        return tuple(sorted(declared))

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "layout_path": list(self.layout_path),
            "instantiation_path": list(self.instantiation_path),
            "visibility": self.visibility.value,
            "panel_id": self.panel_id,
            "description": self.description,
            "metadata": dict(self.metadata),
        }


def _resolve_segments(segments: Sequence[str], selectors: Mapping[str, str]) -> Tuple[str, ...]:
    resolved: list[str] = []
    for segment in segments:
        try:
            rendered = segment.format_map(_SelectorDict(selectors))
        except KeyError as exc:  # pragma: no cover - defensive
            missing = exc.args[0]
            raise PathSpecResolutionError(
                f"Missing selector '{missing}' for path segment '{segment}'."
            ) from exc
        except ValueError as exc:
            raise PathSpecResolutionError(f"Invalid format string '{segment}': {exc}") from exc
        missing = _PLACEHOLDER_PATTERN.findall(segment)
        for placeholder in missing:
            if placeholder not in selectors:
                raise PathSpecResolutionError(
                    f"Missing selector '{placeholder}' for path segment '{segment}'."
                )
        if rendered == "":
            continue
        resolved.append(rendered)
    return tuple(resolved)


class _SelectorDict(dict):
    """Format helper that raises PathSpecResolutionError for missing keys."""

    def __missing__(self, key: str) -> str:
        raise KeyError(key)


def resolve_pathspec(
    pathspec: PathSpec,
    *,
    selectors: Mapping[str, str],
    root: Path | None = None,
    private_root: Path | None = None,
    location: str = "instantiation",
) -> Path:
    """Resolve a PathSpec into an absolute or relative path."""

    if location not in {"instantiation", "layout"}:
        raise ValueError("location must be 'instantiation' or 'layout'")

    missing = [name for name in pathspec.required_selectors() if name not in selectors]
    if missing:
        missing_display = ", ".join(sorted(missing))
        raise PathSpecResolutionError(
            f"PathSpec '{pathspec.id}' missing selectors: {missing_display}"
        )

    segments = (
        pathspec.instantiation_path if location == "instantiation" else pathspec.layout_path
    )
    resolved_segments = _resolve_segments(segments, selectors)

    if location == "layout" or root is None:
        return Path(*resolved_segments)

    base = root if pathspec.visibility is Visibility.PUBLIC else private_root or root
    return base.joinpath(*resolved_segments)
