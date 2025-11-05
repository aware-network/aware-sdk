"""Gemini provider adapter."""

from __future__ import annotations

import os
from uuid import uuid4

from aware_terminal.providers import TerminalProviderInfo, registry

from ...core import ProviderAdapter, ProviderContext
from ...core.installer import InstallRequest, ensure_installed
from ...core.version import get_channel_info
from .metadata import AUTO_INSTALL_ENV, BINARY_NAME, PACKAGE_NAME, SUMMARY, SUPPORTED_CHANNEL, VERSION_ARGS


class GeminiProvider(ProviderAdapter):
    def __init__(self) -> None:
        info = TerminalProviderInfo(
            slug="gemini",
            title="Google Gemini",
            description=SUMMARY,
        )
        install_request = InstallRequest(
            package=PACKAGE_NAME,
            binary_name=BINARY_NAME,
            version_args=VERSION_ARGS,
        )
        super().__init__(info, install_request=install_request)

    def install(self):  # type: ignore[override]
        auto = os.environ.get(AUTO_INSTALL_ENV) == "1"
        request = self.install_request
        if request is None:
            return self.build_result(
                False,
                "Install metadata missing for Gemini provider.",
                data={"auto_install": auto},
            )
        result = ensure_installed(request, auto_install=auto)
        installed = result.version
        data = {
            "package": PACKAGE_NAME,
            "binary": BINARY_NAME,
            "version": installed,
            "command": result.command,
            "binary_path": result.binary_path,
            "auto_install": auto,
        }
        target = os.environ.get("AWARE_TERMINAL_GEMINI_CHANNEL", SUPPORTED_CHANNEL)
        data["channel"] = target
        channel_info = get_channel_info("gemini", channel=target)
        if channel_info.version:
            data["channel_version"] = channel_info.version
        release_notes = self.select_release_notes(channel_info, installed)
        if release_notes:
            data["release_notes"] = release_notes
        return self.build_result(result.success, result.message, data=data)

    def update(self):  # type: ignore[override]
        auto = os.environ.get(AUTO_INSTALL_ENV) == "1"
        target = os.environ.get("AWARE_TERMINAL_GEMINI_CHANNEL", SUPPORTED_CHANNEL)
        channel_info = get_channel_info("gemini", channel=target)
        npm_tag = channel_info.npm_tag or target
        package = PACKAGE_NAME if npm_tag == "latest" else f"{PACKAGE_NAME}@{npm_tag}"
        request = InstallRequest(
            package=package,
            binary_name=BINARY_NAME,
            version_args=VERSION_ARGS,
        )
        result = ensure_installed(request, auto_install=auto, force=True)
        installed = result.version
        data = {
            "package": package,
            "binary": BINARY_NAME,
            "version": installed,
            "command": result.command,
            "binary_path": result.binary_path,
            "auto_install": auto,
            "force": True,
            "channel": target,
        }
        if channel_info.version:
            data["channel_version"] = channel_info.version
        release_notes = self.select_release_notes(channel_info, installed)
        if release_notes:
            data["release_notes"] = release_notes
        return self.build_result(result.success, result.message, data=data)

    def resume(self, *, session_id=None, context: ProviderContext | None = None):  # type: ignore[override]
        install_status = self.evaluate_installation()
        binary = (install_status.binary_path if install_status and install_status.binary_path else BINARY_NAME)
        command = [binary]
        metadata = {
            "provider": self.info.slug,
            "package": PACKAGE_NAME,
            "resume": True,
            "auto_install_env": AUTO_INSTALL_ENV,
        }
        if install_status:
            if install_status.binary_path:
                metadata["binary_path"] = install_status.binary_path
            if install_status.version:
                metadata["version"] = install_status.version
        else:
            metadata["binary_missing"] = True

        target = os.environ.get("AWARE_TERMINAL_GEMINI_CHANNEL", SUPPORTED_CHANNEL)
        metadata["channel"] = target
        channel_info = get_channel_info("gemini", channel=target)
        release_notes = self.select_release_notes(channel_info, metadata.get("version"))
        if release_notes:
            metadata["release_notes"] = release_notes

        resolved = session_id or self.resolve_session_id(context)
        if resolved:
            command.extend(["resume", resolved])
            sid = resolved
        else:
            metadata["resume_manual"] = True
            sid = f"{self.info.slug}-resume"

        return self.build_session_result(
            session_id=sid,
            command=command,
            metadata=metadata,
            context=context,
        )

    def launch(self, *, resume: bool = False, context: ProviderContext | None = None):  # type: ignore[override]
        install_status = self.evaluate_installation()
        binary = (install_status.binary_path if install_status and install_status.binary_path else BINARY_NAME)
        metadata = {
            "provider": self.info.slug,
            "package": PACKAGE_NAME,
            "resume": resume,
            "auto_install_env": AUTO_INSTALL_ENV,
        }
        if install_status:
            if install_status.binary_path:
                metadata["binary_path"] = install_status.binary_path
            if install_status.version:
                metadata["version"] = install_status.version
            if not install_status.success:
                metadata["binary_missing"] = True
        else:
            metadata["binary_missing"] = True

        target = os.environ.get("AWARE_TERMINAL_GEMINI_CHANNEL", SUPPORTED_CHANNEL)
        metadata["channel"] = target
        channel_info = get_channel_info("gemini", channel=target)
        release_notes = self.select_release_notes(channel_info, metadata.get("version"))
        if release_notes:
            metadata["release_notes"] = release_notes

        command = [binary]
        if resume:
            command.extend(["resume", "--last"])
            metadata["resume_request"] = True
            sid = f"{self.info.slug}-resume-request"
        else:
            sid = f"{self.info.slug}-{uuid4().hex}"

        return self.build_session_result(
            session_id=sid,
            command=command,
            metadata=metadata,
            context=context,
        )


registry.register(GeminiProvider())
