"""Tests for aware_environment.renderer module."""

from __future__ import annotations

from pathlib import Path

import pytest

from aware_environment import (
    Environment,
    ObjectFunctionSpec,
    ObjectSpec,
    PathSpec,
    ProtocolSpec,
    RoleSpec,
    RuleSpec,
    Visibility,
)
from aware_environment.renderer import render_rule_fragments, render_rules, render_role_bundle


def _build_sample_environment(tmp_path: Path) -> Environment:
    env = Environment.empty()

    rule_path = tmp_path / "rule.md"
    rule_path.write_text(
        "---\n"
        "id: rule.test\n"
        "title: Test Rule\n"
        "summary: Sample rule summary.\n"
        "---\n\n"
        "## Section\n\n"
        "Content.",
        encoding="utf-8",
    )

    env.bind_rules(
        [
            RuleSpec(
                id="rule.test",
                title="Test Rule",
                path=rule_path,
                summary="Sample rule summary.",
            )
        ]
    )

    protocol_path = tmp_path / "protocol.md"
    protocol_path.write_text(
        "# Protocol Body\n",
        encoding="utf-8",
    )

    env.bind_protocols(
        [
            ProtocolSpec(
                id="protocol-test",
                slug="protocol-test",
                title="Test Protocol",
                path=protocol_path,
                summary="Sample protocol summary.",
            )
        ]
    )

    env.bind_roles(
        [
            RoleSpec(
                slug="sample-role",
                title="Sample Role",
                description="Role description.",
                policy_ids=("rule.test",),
                protocol_ids=("protocol-test",),
            )
        ]
    )

    env.bind_objects(
        [
            ObjectSpec(
                type="task",
                description="Task operations.",
                functions=(
                    ObjectFunctionSpec(
                        name="analysis",
                        description="Capture task analysis notes.",
                        metadata={
                            "policy": "02-task-01-lifecycle",
                            "rule_ids": ("rule.test",),
                            "selectors": ("project", "task"),
                            "flags": (("--title", "Document title"),),
                            "examples": ("aware-cli object call --type task --id demo/sample --function analysis",),
                        },
                    ),
                ),
                pathspecs=(
                    PathSpec(
                        id="task-analysis",
                        layout_path=("docs", "projects", "{project}", "tasks", "{task}", "analysis"),
                        instantiation_path=("docs", "projects", "{project}", "tasks", "{task}", "analysis"),
                        visibility=Visibility.PUBLIC,
                        description="Task analysis entries.",
                    ),
                ),
            ),
        ]
    )

    return env


def test_render_rule_fragments_for_rule(tmp_path: Path) -> None:
    env = _build_sample_environment(tmp_path)

    output = render_rule_fragments(env, rule_ids=["rule.test"])

    assert "## Rule rule.test" in output
    assert "| `analysis` | Capture task analysis notes." in output
    assert "**Flags:**" in output
    assert "`--title` — Document title" in output


def test_render_rule_fragments_for_function(tmp_path: Path) -> None:
    env = _build_sample_environment(tmp_path)

    output = render_rule_fragments(env, function_refs=[("task", "analysis")])

    assert output.startswith("#### `analysis`")
    assert "**Policy:** `rule.test`" in output


def test_render_rule_fragments_for_object(tmp_path: Path) -> None:
    env = _build_sample_environment(tmp_path)

    output = render_rule_fragments(env, object_types=["task"])

    assert "## task" in output
    assert "**Filesystem Layout**" in output
    assert "`task-analysis`" in output


def test_render_rule_fragments_requires_selector(tmp_path: Path) -> None:
    env = _build_sample_environment(tmp_path)

    with pytest.raises(ValueError):
        render_rule_fragments(env)


def test_render_rules_returns_rule_document(tmp_path: Path) -> None:
    env = _build_sample_environment(tmp_path)

    output = render_rules(env, ["rule.test"])

    assert "## Test Rule" in output
    assert "## Section" in output
    assert "Content." in output


def test_render_role_bundle_includes_fragments(tmp_path: Path) -> None:
    env = _build_sample_environment(tmp_path)

    output = render_role_bundle(env, ("sample-role",))

    assert "### Role 1" in output
    assert "Role description." in output
    assert "Capture task analysis notes" in output
    assert "**Protocols:**" in output
    assert "- [Test Protocol]" in output
    assert "Sample protocol summary." in output
