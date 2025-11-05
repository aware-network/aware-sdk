"""Seed helpers for materialising environment artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Mapping

from .environment import Environment
from .pathspec import PathSpec, Visibility, resolve_pathspec

SelectorProvider = Callable[[PathSpec], Mapping[str, str]]


def seed_environment(
    environment: Environment,
    root: Path,
    *,
    include_private: bool = False,
    private_root: Path | None = None,
    global_selectors: Mapping[str, str] | None = None,
    selector_map: Mapping[str, Mapping[str, str]] | None = None,
    selector_provider: SelectorProvider | None = None,
) -> None:
    """Materialise environment pathspecs onto disk.

    Parameters:
        environment: The environment to seed.
        root: Base path for public artifacts.
        include_private: When False, private pathspecs are skipped.
        private_root: Optional base for private artifacts (defaults to ``root``).
        global_selectors: Selectors applied to every pathspec.
        selector_map: Per-pathspec selectors (keyed by ``pathspec.id``).
        selector_provider: Callback invoked per pathspec to supply selectors.
    """

    root.mkdir(parents=True, exist_ok=True)
    private_base = private_root or root

    for obj in environment.objects.list():
        for pathspec in obj.pathspecs:
            if pathspec.visibility is Visibility.PRIVATE and not include_private:
                continue

            selectors: dict[str, str] = {}
            if global_selectors:
                selectors.update(global_selectors)
            if selector_map and pathspec.id in selector_map:
                selectors.update(selector_map[pathspec.id])
            if selector_provider:
                selectors.update(selector_provider(pathspec))

            target = resolve_pathspec(
                pathspec,
                selectors=selectors,
                root=root,
                private_root=private_base,
                location="instantiation",
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                template = pathspec.metadata.get("template")
                initial = str(template) if isinstance(template, str) else ""
                target.write_text(initial, encoding="utf-8")


def iter_pathspecs(environment: Environment) -> Iterable[PathSpec]:
    for obj in environment.objects.list():
        yield from obj.pathspecs
