from dataclasses import dataclass

import pytest

from aware_terminal.core.config import ToolConfig
from types import SimpleNamespace

from aware_terminal.remediation.actions.providers import provider_actions_factory
from aware_terminal.remediation.models import RemediationContext, RemediationPolicy, SetupState


@dataclass
class FakeProviderInfo:
    slug: str
    title: str
    description: str = ""


class FakeResult:
    def __init__(self, success: bool, message: str):
        self.success = success
        self.message = message
        self.data = {}


def make_context(auto: bool, policy: RemediationPolicy) -> RemediationContext:
    return RemediationContext(
        config=ToolConfig(),
        auto=auto,
        platform="linux",
        provider_policy=policy,
        state=SetupState(),
    )


def test_provider_action_manual_when_auto_disabled(monkeypatch):
    monkeypatch.setattr(
        "aware_terminal.remediation.actions.providers.list_providers",
        lambda: [FakeProviderInfo(slug="codex", title="OpenAI Codex")],
    )
    monkeypatch.setattr(
        "aware_terminal.remediation.actions.providers.get_provider",
        lambda slug: None,
    )
    monkeypatch.setattr(
        "aware_terminal.remediation.actions.providers.get_channel_info",
        lambda slug, channel="latest": SimpleNamespace(
            version="1.2.3",
            npm_tag="latest",
            updated_at="2025-10-25T00:00:00Z",
            release_notes={"summary": "Minor improvements"},
            extra={},
        ),
    )
    context = make_context(auto=False, policy=RemediationPolicy.APPLY)
    actions = provider_actions_factory(context)
    assert len(actions) == 1
    outcome = actions[0].run(context)
    assert outcome.status.value == "manual"
    assert outcome.command == [
        "aware-cli",
        "terminal",
        "providers",
        "install",
        "codex",
    ]


def test_provider_action_executes_when_auto(monkeypatch):
    monkeypatch.setattr(
        "aware_terminal.remediation.actions.providers.list_providers",
        lambda: [FakeProviderInfo(slug="codex", title="OpenAI Codex")],
    )
    monkeypatch.setattr(
        "aware_terminal.remediation.actions.providers.get_provider",
        lambda slug: None,
    )
    monkeypatch.setattr(
        "aware_terminal.remediation.actions.providers.get_channel_info",
        lambda slug, channel="latest": SimpleNamespace(
            version="1.2.3",
            npm_tag="latest",
            updated_at="2025-10-25T00:00:00Z",
            release_notes={"summary": "Minor improvements"},
            extra={},
        ),
    )
    monkeypatch.setattr(
        "aware_terminal.remediation.actions.providers.run_provider_action",
        lambda slug, action: FakeResult(True, "installed"),
    )
    context = make_context(auto=True, policy=RemediationPolicy.APPLY)
    actions = provider_actions_factory(context)
    outcome = actions[0].run(context)
    assert outcome.status.value == "executed"
    assert outcome.command is None
    assert outcome.details["provider"] == "codex"


def test_provider_action_up_to_date(monkeypatch):
    provider = SimpleNamespace(evaluate_installation=lambda: SimpleNamespace(version="1.2.3"))

    monkeypatch.setattr(
        "aware_terminal.remediation.actions.providers.list_providers",
        lambda: [FakeProviderInfo(slug="codex", title="OpenAI Codex")],
    )
    monkeypatch.setattr(
        "aware_terminal.remediation.actions.providers.get_provider",
        lambda slug: provider,
    )
    monkeypatch.setattr(
        "aware_terminal.remediation.actions.providers.get_channel_info",
        lambda slug, channel="latest": SimpleNamespace(
            version="1.2.3",
            npm_tag="latest",
            updated_at="2025-10-25T00:00:00Z",
            release_notes={"summary": "Minor improvements"},
            extra={},
        ),
    )

    def fail_run(*_args, **_kwargs):  # pragma: no cover - should not be invoked
        raise AssertionError("run_provider_action should not be called when provider is current")

    monkeypatch.setattr(
        "aware_terminal.remediation.actions.providers.run_provider_action",
        fail_run,
    )

    context = make_context(auto=True, policy=RemediationPolicy.APPLY)
    actions = provider_actions_factory(context)
    outcome = actions[0].run(context)
    assert outcome.status.value == "executed"
    assert outcome.command is None
    assert outcome.message == "Already up to date."
