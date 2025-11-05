"""Codex provider adapter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from uuid import uuid4

from aware_terminal.providers import TerminalProviderInfo, registry

from ...core import ProviderAdapter, ProviderContext, get_channel_info
from ...core.installer import InstallRequest, ensure_installed, evaluate_installation
from .metadata import AUTO_INSTALL_ENV, BINARY_NAME, PACKAGE_NAME, SUMMARY, SUPPORTED_CHANNEL, VERSION_ARGS
from .session_resolver import SessionInfo, resolve_codex_session


class CodexProvider(ProviderAdapter):
    def __init__(self) -> None:
        info = TerminalProviderInfo(
            slug="codex",
            title="OpenAI Codex",
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
                "Install metadata missing for Codex provider.",
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
        channel = os.environ.get("AWARE_TERMINAL_CODEX_CHANNEL", SUPPORTED_CHANNEL)
        channel_info = get_channel_info("codex", channel=channel)
        data["channel"] = channel
        release_notes = self.select_release_notes(channel_info, installed)
        if release_notes:
            data["release_notes"] = release_notes
        return self.build_result(result.success, result.message, data=data)

    def update(self):  # type: ignore[override]
        auto = os.environ.get(AUTO_INSTALL_ENV) == "1"
        request = self.install_request
        if request is None:
            return self.build_result(
                False,
                "Install metadata missing for Codex provider.",
                data={"auto_install": auto, "force": True},
            )
        result = ensure_installed(
            request,
            auto_install=auto,
            force=True,
        )
        installed = result.version
        data = {
            "package": PACKAGE_NAME,
            "binary": BINARY_NAME,
            "version": installed,
            "command": result.command,
            "binary_path": result.binary_path,
            "auto_install": auto,
            "force": True,
        }
        channel = os.environ.get("AWARE_TERMINAL_CODEX_CHANNEL", SUPPORTED_CHANNEL)
        channel_info = get_channel_info("codex", channel=channel)
        data["channel"] = channel
        release_notes = self.select_release_notes(channel_info, installed)
        if release_notes:
            data["release_notes"] = release_notes
        return self.build_result(result.success, result.message, data=data)

    def resume(self, *, session_id=None, context: ProviderContext | None = None):  # type: ignore[override]
        request = self.install_request
        install_status = evaluate_installation(request) if request else None
        resolved_id, resolution_source, env_snapshot, detected = self._resolve_session(context, explicit=session_id)
        binary = (install_status.binary_path if install_status and install_status.binary_path else None) or BINARY_NAME
        command = [binary, "exec", "resume"]
        channel = os.environ.get("AWARE_TERMINAL_CODEX_CHANNEL", SUPPORTED_CHANNEL)
        channel_info = get_channel_info("codex", channel=channel)
        metadata = {
            "provider": self.info.slug,
            "package": PACKAGE_NAME,
            "resume": True,
            "auto_install_env": AUTO_INSTALL_ENV,
        }
        if install_status and install_status.binary_path:
            metadata["binary_path"] = install_status.binary_path
        if install_status and install_status.version:
            metadata["version"] = install_status.version
        else:
            metadata["binary_missing"] = True
        metadata["channel"] = channel
        release_notes = self.select_release_notes(channel_info, metadata.get("version"))
        if release_notes:
            metadata["release_notes"] = release_notes

        resolution_meta = {"source": resolution_source}
        env: Dict[str, str] = {}
        if detected and detected.log_path:
            env["CODEX_SESSION_LOG"] = str(detected.log_path)
            resolution_meta["log_path"] = str(detected.log_path)
        elif env_snapshot.get("CODEX_SESSION_LOG"):
            env["CODEX_SESSION_LOG"] = env_snapshot["CODEX_SESSION_LOG"]
            resolution_meta["log_path"] = env_snapshot["CODEX_SESSION_LOG"]
        if detected and detected.pid is not None:
            env["CODEX_SESSION_PID"] = str(detected.pid)
            resolution_meta["pid"] = str(detected.pid)
        elif env_snapshot.get("CODEX_SESSION_PID"):
            env["CODEX_SESSION_PID"] = env_snapshot["CODEX_SESSION_PID"]
            resolution_meta["pid"] = env_snapshot["CODEX_SESSION_PID"]

        if resolved_id:
            command.append(resolved_id)
            sid = resolved_id
            env["AWARE_PROVIDER_SESSION_ID"] = resolved_id
            env["CODEX_SESSION_ID"] = resolved_id
            resolution_meta["session_id"] = resolved_id
        else:
            command.append("--last")
            sid = f"{self.info.slug}-last"
            metadata["resume_last"] = True
            resolution_meta["fallback"] = "last"

        if env_snapshot:
            metadata.setdefault("provider_env", env_snapshot)
        metadata["session_resolution"] = resolution_meta

        return self.build_session_result(
            session_id=sid,
            command=command,
            env=env or None,
            metadata=metadata,
            context=context,
        )

    def launch(self, *, resume: bool = False, context: ProviderContext | None = None):  # type: ignore[override]
        request = self.install_request
        install_status = evaluate_installation(request) if request else None
        binary = (install_status.binary_path if install_status and install_status.binary_path else None) or BINARY_NAME
        channel = os.environ.get("AWARE_TERMINAL_CODEX_CHANNEL", SUPPORTED_CHANNEL)
        channel_info = get_channel_info("codex", channel=channel)
        metadata = {
            "provider": self.info.slug,
            "package": PACKAGE_NAME,
            "resume": False,
            "auto_install_env": AUTO_INSTALL_ENV,
        }
        if install_status and install_status.binary_path:
            metadata["binary_path"] = install_status.binary_path
        if install_status and install_status.version:
            metadata["version"] = install_status.version
        if not (install_status and install_status.success):
            metadata["binary_missing"] = True
        metadata["channel"] = channel
        release_notes = self.select_release_notes(channel_info, metadata.get("version"))
        if release_notes:
            metadata["release_notes"] = release_notes

        command = [binary]
        if resume:
            command.extend(["exec", "resume", "--last"])
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

    # Session resolution helpers -------------------------------------------------

    def resolve_active_session(self, *, context: Optional[ProviderContext] = None):
        session_id, source, env_map, session_info = self._resolve_session(context, explicit=None)
        resolution_meta: Dict[str, str] = {"source": source}
        if session_info and session_info.log_path:
            resolution_meta["log_path"] = str(session_info.log_path)
        if session_info and session_info.pid is not None:
            resolution_meta["pid"] = str(session_info.pid)

        if not session_id:
            return self.build_result(
                False,
                "No active Codex session detected.",
                data={
                    "provider": self.info.slug,
                    "resolution": resolution_meta,
                },
            )

        payload: Dict[str, object] = {
            "provider": self.info.slug,
            "session_id": session_id,
            "env": env_map,
            "resolution": resolution_meta,
        }
        if context and context.thread_id:
            payload["thread_id"] = context.thread_id
        if context and context.terminal_id:
            payload["terminal_id"] = context.terminal_id
        if context and context.apt_id:
            payload["apt_id"] = context.apt_id

        return self.build_result(
            True,
            "Resolved active Codex session.",
            data=payload,
        )

    def _resolve_session(
        self,
        context: Optional[ProviderContext],
        *,
        explicit: Optional[str] = None,
    ) -> Tuple[Optional[str], str, Dict[str, str], Optional[SessionInfo]]:
        if explicit:
            env_map: Dict[str, str] = {
                "AWARE_PROVIDER_SESSION_ID": explicit,
                "CODEX_SESSION_ID": explicit,
            }
            return explicit, "explicit", env_map, None

        descriptor = self._ensure_context_descriptor(context)
        if descriptor is not None and descriptor.provider.session_id:
            env_map = dict(descriptor.provider.env or {})
            return descriptor.provider.session_id, "descriptor", env_map, None

        session_info = resolve_codex_session()
        if session_info is None:
            return None, "unresolved", {}, None

        env_map = {
            "AWARE_PROVIDER_SESSION_ID": session_info.session_id,
            "CODEX_SESSION_ID": session_info.session_id,
        }
        if session_info.log_path:
            env_map["CODEX_SESSION_LOG"] = str(Path(session_info.log_path))
        if session_info.pid is not None:
            env_map["CODEX_SESSION_PID"] = str(session_info.pid)

        descriptor = self._persist_descriptor(
            context=context,
            session_id=session_info.session_id,
            env=env_map,
        )
        if descriptor is not None and descriptor.provider.env:
            env_map = dict(descriptor.provider.env)
        return session_info.session_id, "detected", env_map, session_info


registry.register(CodexProvider())
