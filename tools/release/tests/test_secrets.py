from __future__ import annotations

from pathlib import Path

import pytest

import aware_release.secrets as secrets


@pytest.fixture()
def isolated_secrets(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(secrets, "_secret_specs", {})
    monkeypatch.setattr(secrets, "_resolvers", [])
    secrets.register_resolver(secrets.EnvResolver(), priority=0, name="env", source="env")
    return secrets


def test_resolve_secret_info_reports_env(monkeypatch: pytest.MonkeyPatch, isolated_secrets) -> None:
    monkeypatch.setenv("TEST_SECRET", "value")
    isolated_secrets.register_secret(secrets.SecretSpec(name="TEST_SECRET"))

    info = isolated_secrets.resolve_secret_info("TEST_SECRET")

    assert info.value == "value"
    assert info.source == "env"
    assert any(attempt.success for attempt in info.attempts)


def test_resolve_secret_info_dotenv(tmp_path: Path, isolated_secrets) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DOT_SECRET=\"abc123\"  # inline comment\n")
    isolated_secrets.use_dotenv(env_file)
    isolated_secrets.register_secret(secrets.SecretSpec(name="DOT_SECRET"))

    info = isolated_secrets.resolve_secret_info("DOT_SECRET")

    assert info.value == "abc123"
    assert info.source == "dotenv"
    assert info.details["path"] == str(env_file)
    assert info.attempts[0].resolver == "env"
    assert not info.attempts[0].success
    assert any(attempt.success and attempt.source == "dotenv" for attempt in info.attempts)


def test_describe_secret_missing_reports_attempts(tmp_path: Path, isolated_secrets) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("MALFORMED_LINE\n")
    isolated_secrets.use_dotenv(env_file)

    payload = isolated_secrets.describe_secret("UNKNOWN_SECRET")

    assert payload["present"] is False
    attempts = payload["attempts"]
    assert len(attempts) == 2  # env + dotenv
    dotenv_attempt = attempts[1]
    assert dotenv_attempt["source"] == "dotenv"
    assert dotenv_attempt["details"]["path"] == str(env_file)
    assert "warnings" in dotenv_attempt["details"]
    assert dotenv_attempt["details"]["warnings"]
