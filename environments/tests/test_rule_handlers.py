from __future__ import annotations

from pathlib import Path

from aware_environment import RuleSpec

from aware_environments.kernel.samples import copy_rule_samples
from aware_environments.kernel.objects.rule import handlers as rule_handlers


def _build_sample_rules(tmp_path: Path) -> tuple[RuleSpec, RuleSpec]:
    rules_root = copy_rule_samples(tmp_path / "rules")
    return (
        RuleSpec(
            id="02-task-01-lifecycle",
            title="Sample Task Lifecycle",
            path=(rules_root / "02-task-01-lifecycle.md").resolve(),
            layer="task",
            version="1.0.0",
        ),
        RuleSpec(
            id="04-agent-01-memory-hierarchy",
            title="Sample Agent Memory Hierarchy",
            path=(rules_root / "04-agent-01-memory-hierarchy.md").resolve(),
            layer="agent",
            version="1.0.0",
        ),
    )


def test_list_rules_uses_sample_paths(tmp_path, monkeypatch) -> None:
    sample_rules = _build_sample_rules(tmp_path)
    monkeypatch.setattr(rule_handlers, "RULES", sample_rules)

    payloads = rule_handlers.list_rules()
    ids = {entry["id"] for entry in payloads}
    assert ids == {spec.id for spec in sample_rules}
    for entry in payloads:
        assert Path(entry["path"]).exists()
