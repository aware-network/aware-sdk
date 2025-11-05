"""Metadata constants for the Claude Code provider."""

from ...core.version import get_supported_version

PACKAGE_NAME = "@anthropic-ai/claude-code"
BINARY_NAME = "claude"
VERSION_ARGS = ("--version",)
SUMMARY = "Bridge Claude Code workflows via aware-terminal control center."
AUTO_INSTALL_ENV = "AWARE_TERMINAL_PROVIDERS_AUTO_INSTALL"
SUPPORTED_CHANNEL = "latest"
try:
    SUPPORTED_VERSION = get_supported_version("claude-code", SUPPORTED_CHANNEL)
except Exception:  # pragma: no cover
    SUPPORTED_VERSION = None
