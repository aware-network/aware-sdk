"""Base adapter scaffolding for terminal providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from aware_terminal.providers import (
    ProviderActionResult,
    ProviderContext,
    ProviderSessionResult,
    TerminalProvider,
    TerminalProviderInfo,
)
from .installer import InstallRequest, InstallResult, evaluate_installation
from .descriptor import (
    ProviderDescriptor,
    ProviderDescriptorModel,
    load_provider_descriptor,
    save_provider_descriptor,
)


@dataclass(slots=True)
class ProviderMessage:
    """Lightweight container for standardised action messaging."""

    install: str
    update: str
    resume: str
    launch: str


class ProviderAdapter(TerminalProvider):
    """Base class that offers helper utilities for provider implementations."""

    def __init__(
        self,
        info: TerminalProviderInfo,
        *,
        install_request: Optional[InstallRequest] = None,
    ) -> None:
        super().__init__(info)
        self._install_request: Optional[InstallRequest] = install_request

    @staticmethod
    def build_result(
        success: bool,
        message: str,
        *,
        data: Optional[Dict[str, Any]] = None,
    ) -> ProviderActionResult:
        return ProviderActionResult(success=success, message=message, data=data)

    def not_implemented(
        self, action: str, *, data: Optional[Dict[str, Any]] = None
    ) -> ProviderActionResult:
        message = f"{action} for {self.info.title} is not implemented yet."
        return self.build_result(False, message, data=data)

    def build_session_result(
        self,
        *,
        session_id: str,
        command: Sequence[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[ProviderContext] = None,
    ) -> ProviderSessionResult:
        meta = dict(metadata) if metadata else {}
        if context:
            if context.thread_id:
                meta.setdefault("thread_id", context.thread_id)
            if context.terminal_id:
                meta.setdefault("terminal_id", context.terminal_id)
            if context.apt_id:
                meta.setdefault("apt_id", context.apt_id)
        meta.setdefault("session_id", session_id)
        return ProviderSessionResult(
            session_id=session_id,
            command=list(command),
            cwd=cwd,
            env=dict(env) if env else None,
            metadata=meta,
        )

    def stub_session(
        self,
        action: str,
        *,
        session_id: Optional[str] = None,
        resume: bool = False,
        context: Optional[ProviderContext] = None,
    ) -> ProviderSessionResult:
        sid = session_id or f"{self.info.slug}-stub"
        message = f"{self.info.title} {action.lower()} automation is pending."
        metadata: Dict[str, Any] = {
            "pending": True,
            "action": action.lower(),
        }
        if resume:
            metadata["resume"] = True
        return self.build_session_result(
            session_id=sid,
            command=["echo", message],
            metadata=metadata,
            context=context,
        )

    @property
    def install_request(self) -> Optional[InstallRequest]:
        return self._install_request

    def evaluate_installation(self) -> Optional[InstallResult]:
        if self._install_request is None:
            return None
        return evaluate_installation(self._install_request)

    # Descriptor helpers --------------------------------------------------

    def load_descriptor(self, *, thread_id: Optional[str], terminal_id: Optional[str]) -> Optional[ProviderDescriptor]:
        if not thread_id or not terminal_id:
            return None
        return load_provider_descriptor(thread_id, terminal_id)

    def save_descriptor(
        self,
        *,
        thread_id: Optional[str],
        terminal_id: Optional[str],
        descriptor: ProviderDescriptor,
    ) -> None:
        if not thread_id or not terminal_id:
            return
        save_provider_descriptor(thread_id, terminal_id, descriptor)

    @staticmethod
    def select_release_notes(channel_info, installed_version: Optional[str]):
        notes = getattr(channel_info, 'release_notes', None)
        latest = getattr(channel_info, 'version', None)
        if notes is None:
            return None
        if installed_version and latest and installed_version == latest:
            return None
        if isinstance(notes, dict):
            return notes
        try:
            return notes.model_dump()
        except AttributeError:
            return None

    def resolve_session_id(self, context: Optional[ProviderContext]) -> Optional[str]:
        descriptor = self._ensure_context_descriptor(context)
        if descriptor is None:
            return None
        provider_block = descriptor.provider
        if provider_block.slug != self.info.slug:
            return None
        return provider_block.session_id

    # Context / descriptor utilities ------------------------------------

    def _ensure_context_descriptor(self, context: Optional[ProviderContext]) -> Optional[ProviderDescriptor]:
        if not context:
            return None
        descriptor = self._coerce_descriptor(context.descriptor)
        if descriptor is not None:
            context.descriptor = descriptor
            return descriptor
        if context.thread_id and context.terminal_id:
            descriptor = self.load_descriptor(thread_id=context.thread_id, terminal_id=context.terminal_id)
            if descriptor:
                context.descriptor = descriptor
        return descriptor

    @staticmethod
    def _coerce_descriptor(raw: Any) -> Optional[ProviderDescriptor]:
        if raw is None:
            return None
        if isinstance(raw, ProviderDescriptor):
            return raw
        if isinstance(raw, ProviderDescriptorModel):
            return ProviderDescriptor(provider=raw)
        if isinstance(raw, dict):
            try:
                return ProviderDescriptor.model_validate(raw)
            except Exception:
                return None
        return None

    def _persist_descriptor(
        self,
        *,
        context: Optional[ProviderContext],
        session_id: str,
        env: Optional[Dict[str, str]] = None,
        updates: Optional[Dict[str, Any]] = None,
    ) -> Optional[ProviderDescriptor]:
        descriptor = self._ensure_context_descriptor(context)
        if descriptor is not None:
            provider_model = descriptor.provider.model_copy(deep=True)
        else:
            provider_model = ProviderDescriptorModel(
                slug=self.info.slug,
                session_id=session_id,
                env={},
            )

        env_map = dict(provider_model.env or {})
        if env:
            for key, value in env.items():
                if value is None:
                    continue
                env_map[str(key)] = str(value)
        env_map.setdefault("AWARE_PROVIDER_SESSION_ID", session_id)
        provider_model = provider_model.model_copy(
            update={
                "session_id": session_id,
                "env": env_map,
            }
        )
        if updates:
            provider_model = provider_model.model_copy(update=updates)

        descriptor = ProviderDescriptor(provider=provider_model)

        if context and context.thread_id and context.terminal_id:
            self.save_descriptor(
                thread_id=context.thread_id,
                terminal_id=context.terminal_id,
                descriptor=descriptor,
            )
        if context is not None:
            context.descriptor = descriptor
        return descriptor

    # Resolution ---------------------------------------------------------

    def resolve_active_session(
        self,
        *,
        context: Optional[ProviderContext] = None,
    ) -> ProviderActionResult:
        descriptor = self._ensure_context_descriptor(context)
        session_id = self.resolve_session_id(context)
        source = "descriptor" if session_id else "unresolved"
        env_map: Dict[str, str] = {}
        if descriptor and descriptor.provider.env:
            env_map.update({str(k): str(v) for k, v in descriptor.provider.env.items() if v is not None})
        if session_id:
            env_map.setdefault("AWARE_PROVIDER_SESSION_ID", session_id)
        resolution = {"source": source, "provider": self.info.slug}
        payload: Dict[str, Any] = {
            "provider": self.info.slug,
            "resolution": resolution,
        }
        if session_id:
            payload["session_id"] = session_id
            payload["env"] = env_map
        if context:
            if context.thread_id:
                payload["thread_id"] = context.thread_id
            if context.terminal_id:
                payload["terminal_id"] = context.terminal_id
            if context.apt_id:
                payload["apt_id"] = context.apt_id

        if session_id:
            return self.build_result(True, "Resolved provider session from descriptor.", data=payload)
        return self.build_result(False, "No active provider session detected.", data=payload)
