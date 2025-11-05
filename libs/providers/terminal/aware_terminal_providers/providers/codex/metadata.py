"""Metadata constants for the Codex provider."""

from ...core.version import get_supported_version

PACKAGE_NAME = "@openai/codex"
BINARY_NAME = "codex"
VERSION_ARGS = ("--version",)
SUMMARY = "Run OpenAI's coding assistant inside aware-terminal sessions."
AUTO_INSTALL_ENV = "AWARE_TERMINAL_PROVIDERS_AUTO_INSTALL"
SUPPORTED_CHANNEL = "latest"
try:
    SUPPORTED_VERSION = get_supported_version("codex", SUPPORTED_CHANNEL)
except Exception:  # pragma: no cover - fallback when manifest missing
    SUPPORTED_VERSION = None
