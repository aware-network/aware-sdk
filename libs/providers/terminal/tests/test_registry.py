import json
from pathlib import Path

from aware_terminal.providers import ProviderContext
from aware_terminal_providers import ProviderActionResult, ProviderSessionResult, registry
from aware_terminal_providers.core import descriptor as descriptor_module
from aware_terminal_providers.providers.codex import adapter as codex_adapter
from aware_terminal_providers.core import get_channel_info, get_supported_version
from aware_terminal_providers.providers.codex import metadata as codex_meta
from aware_terminal_providers.providers.claude_code import metadata as claude_meta
from aware_terminal_providers.providers.gemini import metadata as gemini_meta
from aware_terminal_providers.providers.codex.session_resolver import SessionInfo


def test_stub_providers_registered() -> None:
    providers = {provider.info.slug: provider for provider in registry.list()}
    assert {"codex", "claude-code", "gemini"}.issubset(providers.keys())


def test_stub_provider_returns_placeholder_results() -> None:
    provider = registry.get("codex")
    assert provider is not None

    result = provider.install()
    assert isinstance(result, ProviderActionResult)
    assert result.message
    assert "codex" in result.message.lower()
    assert result.data is None or "package" in result.data


def test_codex_provider_returns_session_spec() -> None:
    provider = registry.get("codex")
    assert provider is not None

    session = provider.launch()
    assert isinstance(session, ProviderSessionResult)
    assert isinstance(session.session_id, str)
    assert session.session_id
    assert session.command
    assert Path(session.command[0]).name == "codex"
    assert session.metadata and session.metadata.get("session_id") == session.session_id


def test_claude_provider_returns_session_spec() -> None:
    provider = registry.get("claude-code")
    assert provider is not None

    session = provider.launch()
    assert isinstance(session, ProviderSessionResult)
    assert session.command
    assert Path(session.command[0]).name == "claude"
    assert session.metadata and session.metadata.get("session_id") == session.session_id


def test_gemini_provider_returns_session_spec() -> None:
    provider = registry.get("gemini")
    assert provider is not None

    session = provider.launch()
    assert isinstance(session, ProviderSessionResult)
    assert session.command
    assert Path(session.command[0]).name == "gemini"
    assert session.metadata and session.metadata.get("session_id") == session.session_id


def test_supported_versions_match_manifest() -> None:
    assert codex_meta.SUPPORTED_VERSION == get_supported_version("codex")
    assert claude_meta.SUPPORTED_VERSION == get_supported_version("claude-code")
    assert gemini_meta.SUPPORTED_VERSION == get_supported_version("gemini")


def test_release_notes_present_when_available() -> None:
    codex_info = get_channel_info("codex")
    assert codex_info.release_notes is not None
    gemini_info = get_channel_info("gemini")
    assert gemini_info.release_notes is not None


def test_codex_resume_detects_session_and_persists_descriptor(monkeypatch, tmp_path) -> None:
    provider = registry.get("codex")
    assert provider is not None

    from aware_terminal_providers.core.installer import InstallResult

    install_result = InstallResult(
        success=True,
        message="codex present",
        version="0.49.0",
        binary_path="/usr/bin/codex",
    )

    monkeypatch.setattr(codex_adapter, "evaluate_installation", lambda request: install_result)

    log_path = tmp_path / "sessions" / "2025" / "log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("{}", encoding="utf-8")

    session_info = SessionInfo(session_id="019a12df-a61e-77c3-9337-5c4090f58c9c", log_path=log_path, pid=4321)
    calls = {"count": 0}

    def fake_resolver() -> SessionInfo:
        calls["count"] += 1
        return session_info

    monkeypatch.setattr(codex_adapter, "resolve_codex_session", fake_resolver)
    monkeypatch.setattr(descriptor_module, "DESCRIPTOR_ROOT", tmp_path)

    context = ProviderContext(thread_id="thread-1", terminal_id="terminal-1", apt_id="apt-1")

    resolution_result = provider.resolve_active_session(context=context)

    assert resolution_result.success
    assert resolution_result.data is not None
    assert resolution_result.data.get("session_id") == session_info.session_id
    assert resolution_result.data.get("env")["CODEX_SESSION_ID"] == session_info.session_id
    assert resolution_result.data.get("resolution")["source"] == "detected"

    descriptor_path = tmp_path / "thread-1" / "terminals" / "terminal-1.json"
    assert descriptor_path.exists()
    payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    provider_block = payload["provider"]
    assert provider_block["session_id"] == session_info.session_id
    assert provider_block["env"]["CODEX_SESSION_ID"] == session_info.session_id
    assert provider_block["env"]["CODEX_SESSION_LOG"] == str(log_path)
    assert provider_block["env"]["CODEX_SESSION_PID"] == str(session_info.pid)

    result = provider.resume(context=context)

    assert calls["count"] == 1
    assert result.session_id == session_info.session_id
    assert result.command[-1] == session_info.session_id

    env_map = result.environment
    assert env_map["AWARE_PROVIDER_SESSION_ID"] == session_info.session_id
    assert env_map["CODEX_SESSION_LOG"] == str(log_path)
    assert env_map["CODEX_SESSION_PID"] == str(session_info.pid)

    resolution = result.metadata.get("session_resolution", {})
    assert resolution.get("source") == "descriptor"
    assert resolution.get("session_id") == session_info.session_id
    assert resolution.get("log_path") == str(log_path)
