from __future__ import annotations

import os
from typing import Any, Dict

import pytest

from aware_release import secrets
from aware_release.workflows import (
    WorkflowDispatchResult,
    WorkflowInputSpec,
    WorkflowSpec,
    WorkflowTriggerError,
    trigger_workflow,
)


@pytest.fixture(autouse=True)
def _isolate_secret_resolvers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets, "_resolvers", [])
    secrets.register_resolver(secrets.EnvResolver(), priority=0, name="env", source="env")


class _FakeResponse:
    def __init__(self, status_code: int = 204, headers: Dict[str, str] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self.reason = "OK"


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, headers: dict[str, str], json: dict[str, Any], timeout: int) -> _FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _FakeResponse()


def test_trigger_workflow_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN_RELEASE", "token-123")
    session = _FakeSession()
    spec = WorkflowSpec(
        slug="cli-release",
        repo="aware-network/aware",
        workflow="release-cli.yml",
        inputs={
            "channel": WorkflowInputSpec(required=True),
            "version": WorkflowInputSpec(default="0.1.0"),
        },
    )

    result = trigger_workflow(
        spec,
        inputs={"channel": "dev"},
        session=session,  # type: ignore[arg-type]
    )

    assert isinstance(result, WorkflowDispatchResult)
    assert result.status == "dispatched"
    assert result.inputs == {"channel": "dev", "version": "0.1.0"}
    assert session.calls[0]["json"] == {"ref": "main", "inputs": {"channel": "dev", "version": "0.1.0"}}


def test_trigger_workflow_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_TOKEN_RELEASE", raising=False)
    spec = WorkflowSpec(slug="cli-release", repo="aware-network/aware", workflow="release-cli.yml")

    with pytest.raises(WorkflowTriggerError) as excinfo:
        trigger_workflow(spec, inputs={})
    message = str(excinfo.value)
    assert "GH_TOKEN_RELEASE" in message
    assert "Checked resolvers" in message


def test_trigger_workflow_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN_RELEASE", "token-123")
    spec = WorkflowSpec(slug="cli-release", repo="aware-network/aware", workflow="release-cli.yml")

    result = trigger_workflow(spec, dry_run=True)

    assert result.status == "skipped"
    assert result.dry_run
    assert result.response_status is None


def test_trigger_workflow_missing_required_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN_RELEASE", "token-123")
    spec = WorkflowSpec(
        slug="cli-release",
        repo="aware-network/aware",
        workflow="release-cli.yml",
        inputs={"channel": WorkflowInputSpec(required=True)},
    )

    with pytest.raises(WorkflowTriggerError):
        trigger_workflow(spec, inputs={})
