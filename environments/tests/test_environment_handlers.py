from __future__ import annotations

import json
from pathlib import Path

from aware_environment.environment import Environment
from aware_environment.fs import OperationWritePolicy, apply_plan
from aware_environment.rule.spec import RuleSpec
from aware_environment.protocol.spec import ProtocolSpec
from aware_environments.kernel.objects.environment.handlers import (
    render_agent,
    render_role,
    render_rule,
    render_object,
    render_guide,
    render_protocol,
    environment_lock,
    rules_lock,
    describe,
    list_environments,
    apply_patch,
)
from aware_environments.kernel.objects.environment.schemas import (
    RenderAgentPayload,
    RenderGuidePayload,
    RenderRolePayload,
    RenderRulePayload,
    RenderProtocolPayload,
    EnvironmentLockPayload,
    RulesLockPayload,
    DescribeEnvironmentPayload,
    ApplyPatchPayload,
)
from unittest import mock


def _sample_environment(tmp_path: Path) -> Environment:
    from aware_environment.agent.spec import AgentSpec
    from aware_environment.role.spec import RoleSpec

    env = Environment.empty()
    env.bind_agents([AgentSpec(slug="demo-agent", title="Demo Agent", role_slugs=(), description="")])
    env.bind_roles([RoleSpec(slug="demo-role", title="Demo Role", description="", policy_ids=())])
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rule_path = rules_dir / "00-environment.md"
    rule_path.write_text(
        "---\n"
        "id: 00-environment\n"
        "title: Environment Constitution\n"
        "version: 1.0.0\n"
        "updated: 2025-10-30T00:00:00Z\n"
        "---\n\n"
        "Environment constitution body.\n",
        encoding="utf-8",
    )
    env.bind_rules(
        [
            RuleSpec(
                id="00-environment",
                title="Environment Constitution",
                path=rule_path,
                version="1.0.0",
            ),
        ]
    )
    protocols_dir = tmp_path / "protocols"
    protocols_dir.mkdir(parents=True, exist_ok=True)
    protocol_path = protocols_dir / "apt-bootstrap.md"
    protocol_path.write_text("# Protocol body\n", encoding="utf-8")
    env.bind_protocols(
        [
            ProtocolSpec(
                id="protocol-apt-bootstrap",
                slug="apt-bootstrap",
                title="APT Bootstrap Protocol",
                path=protocol_path,
                summary="Bootstrap guidance",
            )
        ]
    )
    env.set_constitution_rule("00-environment")
    env.bind_objects([])
    return env


def test_list_environments_includes_kernel_and_active(tmp_path: Path, monkeypatch):
    kernel_env = _sample_environment(tmp_path)
    active_env = _sample_environment(tmp_path / "active")
    active_entrypoint = "custom.environment:load"

    monkeypatch.setenv("AWARE_ENVIRONMENT_ENTRYPOINT", active_entrypoint)

    with mock.patch(
        "aware_environments.kernel.objects.environment.handlers.load_environment",
        return_value=active_env,
    ):
        result = list_environments(kernel_env)

    assert result.plan is None
    payload = result.payload
    assert isinstance(payload, list)
    kernel_entry = next(entry for entry in payload if entry["id"] == "kernel")
    assert kernel_entry["entrypoint"] == "aware_environments.kernel.registry:get_environment"
    assert kernel_entry["object_count"] >= 0

    active_entry = next(entry for entry in payload if entry["id"] == "active")
    assert active_entry["entrypoint"] == active_entrypoint
    assert active_entry["active"] is True
    assert active_entry.get("load_error") is None


def test_render_agent_handler(tmp_path: Path):
    env = _sample_environment(tmp_path)
    identities_root = tmp_path / "docs" / "identities"
    output_dir = identities_root / "agents" / "demo-agent" / "runtime" / "process" / "main" / "threads" / "main"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = render_agent(
        env,
        agent="demo-agent",
        process="main",
        thread="main",
        identities_root=identities_root,
        heading_level=1,
        context=None,
        output_path=None,
    )

    assert isinstance(result.payload, RenderAgentPayload)
    assert "Agent Rulebook" in result.payload.markdown
    assert result.payload.include_constitution is True
    assert result.plan is not None
    write = result.plan.writes[0]
    assert write.policy is OperationWritePolicy.MODIFIABLE
    assert write.path.name == "AGENT.md"


def test_render_agent_handler_omit_constitution(tmp_path: Path):
    env = _sample_environment(tmp_path)
    identities_root = tmp_path / "docs" / "identities"
    target = tmp_path / "AGENT.omit.md"

    result = render_agent(
        env,
        agent="demo-agent",
        process="main",
        thread="main",
        identities_root=identities_root,
        heading_level=1,
        context=None,
        output_path=target,
        write=True,
        omit_constitution=True,
    )

    assert isinstance(result.payload, RenderAgentPayload)
    assert result.payload.include_constitution is False
    assert result.plan is not None
    write = result.plan.writes[0]
    assert write.path == target.resolve()
    assert "Environment Constitution" not in write.content


def test_render_role_handler(tmp_path: Path):
    env = _sample_environment(tmp_path)
    result = render_role(env, roles=["demo-role"], heading_level=2)
    assert isinstance(result.payload, RenderRolePayload)
    assert "Demo Role" in result.payload.markdown
    assert result.plan is None
    assert result.payload.output_path is None


def test_render_role_handler_with_output(tmp_path: Path):
    env = _sample_environment(tmp_path)
    target = tmp_path / "role.md"
    result = render_role(
        env,
        roles=["demo-role"],
        heading_level=2,
        output_path=target,
        write=True,
    )
    assert isinstance(result.payload, RenderRolePayload)
    assert result.plan is not None
    assert result.payload.output_path == target
    write_paths = [instruction.path for instruction in result.plan.writes]
    assert target.resolve() in write_paths


def test_render_rule_handler(tmp_path: Path):
    env = _sample_environment(tmp_path)
    result = render_rule(env, rule_ids=["00-environment"], fragments=False)
    assert isinstance(result.payload, RenderRulePayload)
    assert "Environment Constitution" in result.payload.markdown
    assert result.plan is None
    assert result.payload.output_path is None


def test_render_rule_handler_with_output(tmp_path: Path):
    env = _sample_environment(tmp_path)
    target = tmp_path / "rule.md"
    result = render_rule(
        env,
        rule_ids=["00-environment"],
        fragments=False,
        output_path=target,
        write=True,
    )
    assert isinstance(result.payload, RenderRulePayload)
    assert result.plan is not None
    assert result.payload.output_path == target
    write_paths = [instruction.path for instruction in result.plan.writes]
    assert target.resolve() in write_paths
    apply_plan(result.plan)


def test_render_rule_handler_emits_patch_for_existing(tmp_path: Path) -> None:
    env = _sample_environment(tmp_path)
    target = tmp_path / "rule.md"
    initial = render_rule(
        env,
        rule_ids=["00-environment"],
        fragments=False,
        output_path=target,
        write=True,
    )
    apply_plan(initial.plan)
    text = target.read_text(encoding="utf-8")
    target.write_text(text + "\nExtra line\n", encoding="utf-8")

    rerender = render_rule(
        env,
        rule_ids=["00-environment"],
        fragments=False,
        output_path=target,
        write=True,
    )
    assert rerender.plan is not None
    assert not rerender.plan.writes
    assert len(rerender.plan.patches) == 1
    apply_plan(rerender.plan)
    rewritten = target.read_text(encoding="utf-8")
    assert "Extra line" not in rewritten


def test_render_protocol_handler(tmp_path: Path):
    env = _sample_environment(tmp_path)
    result = render_protocol(env, protocol_ids=["apt-bootstrap"])  # slug should match registered slug
    assert isinstance(result.payload, RenderProtocolPayload)
    assert "Protocol body" in result.payload.markdown
    assert result.plan is None
    assert result.payload.output_path is None


def test_render_protocol_handler_with_output(tmp_path: Path):
    env = _sample_environment(tmp_path)
    target = tmp_path / "protocol.md"
    result = render_protocol(env, protocol_ids=["apt-bootstrap"], output_path=target, write=True)
    assert isinstance(result.payload, RenderProtocolPayload)
    assert result.plan is not None
    write_paths = [instruction.path for instruction in result.plan.writes]
    assert target.resolve() in write_paths


def test_render_guide_handler(tmp_path: Path):
    env = _sample_environment(tmp_path)
    aware_root = tmp_path / "workspace"
    aware_root.mkdir(parents=True, exist_ok=True)

    result = render_guide(
        env,
        aware_root=aware_root,
        heading_level=1,
        write_primary=True,
        write_cursorrules=True,
    )
    assert isinstance(result.payload, RenderGuidePayload)
    assert "Environment Constitution" in result.payload.markdown
    assert result.plan is not None
    assert {path.name for path in result.payload.written_paths} == {"AGENTS.md", "CLAUDE.md", ".cursorrules"}
    assert set(result.payload.guide_outputs) >= {"AGENTS.md", "CLAUDE.md", ".cursorrules", "AGENTS_GUIDE"}
    writes = {instruction.path.name for instruction in result.plan.writes}
    assert writes == {"AGENTS.md", "CLAUDE.md", ".cursorrules"}


def test_render_guide_handler_compose_agents(tmp_path: Path):
    env = _sample_environment(tmp_path)
    aware_root = tmp_path / "workspace"
    identities_root = aware_root / "docs" / "identities"
    identities_root.mkdir(parents=True, exist_ok=True)

    result = render_guide(
        env,
        aware_root=aware_root,
        heading_level=1,
        write_primary=True,
        write_cursorrules=False,
        compose_agents=True,
        default_agent="demo-agent",
    )

    assert isinstance(result.payload, RenderGuidePayload)
    assert "Default Agent Persona (demo-agent)" in result.payload.markdown
    assert result.payload.guide_outputs.get("default_agent_persona") == "demo-agent"
    assert result.plan is not None
    written = {instruction.path.name for instruction in result.plan.writes}
    assert "AGENTS.md" in written


def test_render_guide_handler_output_only(tmp_path: Path):
    env = _sample_environment(tmp_path)
    aware_root = tmp_path / "workspace"
    aware_root.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "guide.md"

    result = render_guide(
        env,
        aware_root=aware_root,
        heading_level=1,
        write_primary=False,
        write_cursorrules=False,
        output_path=target,
    )

    assert isinstance(result.payload, RenderGuidePayload)
    assert result.payload.output_path == target.resolve()
    assert result.payload.written_paths == [target.resolve()]
    assert result.plan is not None
    assert len(result.plan.writes) == 1
    assert result.plan.writes[0].path == target.resolve()


def test_describe_environment_handler(tmp_path: Path):
    env = _sample_environment(tmp_path)
    result = describe(env)
    assert isinstance(result.payload, DescribeEnvironmentPayload)
    payload = result.payload
    assert payload.agent_count == 1
    assert payload.role_count == 1
    assert payload.rule_count == 1
    assert payload.constitution_rule == "00-environment"


def test_environment_lock_handler(tmp_path: Path):
    env = _sample_environment(tmp_path)
    aware_root = tmp_path / "workspace"
    aware_root.mkdir(parents=True, exist_ok=True)
    aware_dir = aware_root / ".aware"
    aware_dir.mkdir(parents=True, exist_ok=True)
    (aware_dir / "environment.json").write_text(json.dumps({"title": "Aware Kernel"}), encoding="utf-8")
    pyproject = aware_root / "environments" / "pyproject.toml"
    pyproject.parent.mkdir(parents=True, exist_ok=True)
    pyproject.write_text('[project]\nversion = "0.2.0"\n', encoding="utf-8")

    result = environment_lock(env, aware_root=aware_root)
    assert isinstance(result.payload, EnvironmentLockPayload)
    payload = result.payload
    expected_path = aware_root / ".aware" / "ENV.lock"
    assert payload.output_path == expected_path
    assert payload.written_paths == [expected_path]
    assert payload.lock["environment"] == "Aware Kernel"
    assert result.plan is not None
    write_paths = [instruction.path for instruction in result.plan.writes]
    assert expected_path in write_paths
    assert all(instruction.policy is OperationWritePolicy.MODIFIABLE for instruction in result.plan.writes)


def test_rules_lock_handler(tmp_path: Path):
    env = _sample_environment(tmp_path)
    aware_root = tmp_path / "workspace"
    aware_root.mkdir(parents=True, exist_ok=True)
    (aware_root / ".aware").mkdir(parents=True, exist_ok=True)

    result = rules_lock(env, aware_root=aware_root)
    assert isinstance(result.payload, RulesLockPayload)
    payload = result.payload
    expected_path = aware_root / ".aware" / "RULES.lock"
    assert payload.output_path == expected_path
    assert payload.written_paths == [expected_path]
    assert payload.lock["rules"][0]["id"] == "00-environment"
    assert result.plan is not None
    write_paths = [instruction.path for instruction in result.plan.writes]
    assert expected_path in write_paths
    assert all(instruction.policy is OperationWritePolicy.MODIFIABLE for instruction in result.plan.writes)


def test_render_rule_applies_fragments():
    from aware_environments.kernel.registry import get_environment
    from aware_environment.doc.fragments import apply_fragments

    env = get_environment()
    result = render_rule(env, rule_ids=["01-thread-01-runtime"], write=False)

    assert isinstance(result.payload, RenderRulePayload)
    payload = result.payload
    assert payload.fragments_receipt is not None
    assert payload.fragments_receipt["status"] in {"applied", "no_change"}

    rehydrated, receipt = apply_fragments(payload.markdown, environment=env)
    assert rehydrated == payload.markdown
    assert receipt.status in {"no_change", "partial"}


def test_render_rule_includes_argument_flags():
    from aware_environments.kernel.registry import get_environment

    env = get_environment()
    result = render_rule(env, rule_ids=["01-thread-01-runtime"], write=False)
    markdown = result.payload.markdown
    assert "**Flags:**" in markdown
    assert "--runtime-root" in markdown


def test_render_role_includes_policies():
    from aware_environments.kernel.registry import get_environment

    env = get_environment()
    result = render_role(env, roles=["memory-baseline"], write=False)
    markdown = result.payload.markdown
    assert "Policies:**" in markdown or "**Policies:**" in markdown
    assert "memory-baseline" in markdown


def test_render_object_includes_selectors_and_flags():
    from aware_environments.kernel.registry import get_environment

    env = get_environment()
    result = render_object(env, object="thread", write=False)
    markdown = result.payload.markdown
    assert "**Selectors:**" in markdown
    assert "`--runtime-root`" in markdown


def test_apply_patch_handler_executes_plan(tmp_path: Path) -> None:
    target = tmp_path / "doc.md"
    target.write_text("line1\nline2\n", encoding="utf-8")
    diff = (
        "--- a/doc.md\n"
        "+++ b/doc.md\n"
        "@@ -1,2 +1,2 @@\n"
        "-line1\n"
        "+lineX\n"
        " line2\n"
    )

    result = apply_patch(path=target, diff=diff, summary="Test patch")
    assert isinstance(result.payload, ApplyPatchPayload)
    assert result.plan is not None

    receipt = apply_plan(result.plan)
    assert any(getattr(op, "type", "") == "write" for op in receipt.fs_ops)
    assert target.read_text(encoding="utf-8").startswith("lineX\n")


def test_apply_patch_handler_no_change_returns_noop(tmp_path: Path) -> None:
    target = tmp_path / "doc.md"
    target.write_text("content\n", encoding="utf-8")

    result = apply_patch(path=target, diff="")
    assert isinstance(result.payload, ApplyPatchPayload)
    assert result.plan is None
    assert result.payload.status == "noop"
