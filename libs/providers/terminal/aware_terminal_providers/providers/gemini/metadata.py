"""Metadata constants for the Gemini provider."""

from ...core.version import get_supported_version

PACKAGE_NAME = "@google/gemini-cli"
BINARY_NAME = "gemini"
VERSION_ARGS = ("--version",)
SUMMARY = "Launch Gemini coding assistant with session resume support."
AUTO_INSTALL_ENV = "AWARE_TERMINAL_PROVIDERS_AUTO_INSTALL"
SUPPORTED_CHANNEL = "latest"
try:
    SUPPORTED_VERSION = get_supported_version("gemini", SUPPORTED_CHANNEL)
except Exception:  # pragma: no cover
    SUPPORTED_VERSION = None
