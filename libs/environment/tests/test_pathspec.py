"""Tests for PathSpec resolution and seeding helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from aware_environment.exceptions import PathSpecResolutionError
from aware_environment.pathspec import PathSpec, Visibility, resolve_pathspec
from aware_environment.seed import seed_environment
from aware_environment import Environment, ObjectSpec


def test_resolve_pathspec_instantiation(tmp_path: Path) -> None:
    spec = PathSpec(
        id="project-overview",
        layout_path=("docs", "projects", "{project_slug}", "OVERVIEW.md"),
        instantiation_path=("docs", "projects", "{project_slug}", "OVERVIEW.md"),
    )

    path = resolve_pathspec(
        spec,
        selectors={"project_slug": "demo-project"},
        root=tmp_path,
    )

    assert path == tmp_path / "docs" / "projects" / "demo-project" / "OVERVIEW.md"


def test_resolve_pathspec_missing_selector() -> None:
    spec = PathSpec(
        id="project-overview",
        layout_path=("docs", "projects", "{project_slug}", "OVERVIEW.md"),
        instantiation_path=("docs", "projects", "{project_slug}", "OVERVIEW.md"),
    )

    with pytest.raises(PathSpecResolutionError):
        resolve_pathspec(spec, selectors={}, root=Path("/tmp"))


def test_resolve_pathspec_private_root(tmp_path: Path) -> None:
    spec = PathSpec(
        id="project-index",
        layout_path=("docs", "projects", "{project_slug}", "tasks", ".index.json"),
        instantiation_path=("docs", "projects", "{project_slug}", "tasks", ".index.json"),
        visibility=Visibility.PRIVATE,
    )

    private_root = tmp_path / ".aware" / "private"
    path = resolve_pathspec(
        spec,
        selectors={"project_slug": "demo-project"},
        root=tmp_path,
        private_root=private_root,
    )

    assert path == private_root / "docs" / "projects" / "demo-project" / "tasks" / ".index.json"


def test_seed_environment_uses_resolved_paths(tmp_path: Path) -> None:
    environment = Environment.empty()
    environment.bind_objects(
        [
            ObjectSpec(
                type="project",
                description="Project object",
                functions=tuple(),
                pathspecs=(
                    PathSpec(
                        id="project-overview",
                        layout_path=("{projects_root}", "{project_slug}", "OVERVIEW.md"),
                        instantiation_path=("{projects_root}", "{project_slug}", "OVERVIEW.md"),
                        metadata={"selectors": ["projects_root", "project_slug"], "template": "# Overview\n"},
                    ),
                ),
            )
        ]
    )

    seed_environment(
        environment,
        tmp_path,
        global_selectors={"projects_root": "docs/projects"},
        selector_map={"project-overview": {"project_slug": "demo"}},
    )

    expected = tmp_path / "docs/projects" / "demo" / "OVERVIEW.md"
    assert expected.exists()
    assert expected.read_text(encoding="utf-8") == "# Overview\n"


def test_resolve_pathspec_handles_optional_segment(tmp_path: Path) -> None:
    spec = PathSpec(
        id="task-dir",
        layout_path=("docs", "projects", "{project_slug}", "tasks", "{task_bucket}", "{task_slug}"),
        instantiation_path=("{project_slug}", "tasks", "{task_bucket}", "{task_slug}"),
    )

    running = resolve_pathspec(
        spec,
        selectors={"project_slug": "demo", "task_slug": "alpha", "task_bucket": ""},
        root=tmp_path,
    )
    assert running == tmp_path / "demo" / "tasks" / "alpha"

    queued = resolve_pathspec(
        spec,
        selectors={"project_slug": "demo", "task_slug": "alpha", "task_bucket": "_pending"},
        root=tmp_path,
    )
    assert queued == tmp_path / "demo" / "tasks" / "_pending" / "alpha"
