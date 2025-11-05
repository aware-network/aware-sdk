"""Provider interface definitions for aware-terminal."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class ProviderContext:
    thread_id: Optional[str] = None
    terminal_id: Optional[str] = None
    apt_id: Optional[str] = None
    descriptor: Optional[Dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class TerminalProviderInfo:
    """Describes a provider surfaced in aware-terminal CLI."""

    slug: str
    title: str
    description: str


@dataclass(slots=True)
class ProviderActionResult:
    """Result returned by provider automation hooks."""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        payload = {"success": self.success, "message": self.message}
        if self.data is not None:
            payload["data"] = self.data
        return payload


class TerminalProvider(ABC):
    """Abstract contract implemented by terminal providers."""

    def __init__(self, info: TerminalProviderInfo) -> None:
        self._info = info

    @property
    def info(self) -> TerminalProviderInfo:
        return self._info

    @abstractmethod
    def install(self) -> ProviderActionResult:
        """Install provider prerequisites (SDK, binaries, configuration)."""

    @abstractmethod
    def update(self) -> ProviderActionResult:
        """Update provider assets to the latest supported version."""

    @abstractmethod
    def resume(
        self,
        *,
        session_id: Optional[str] = None,
        context: Optional[ProviderContext] = None,
    ) -> "ProviderSessionResult":
        """Resume or reattach to an existing provider session."""

    @abstractmethod
    def launch(
        self,
        *,
        resume: bool = False,
        context: Optional[ProviderContext] = None,
    ) -> "ProviderSessionResult":
        """Launch an interactive provider session (optionally resuming)."""

    @abstractmethod
    def resolve_active_session(
        self,
        *,
        context: Optional[ProviderContext] = None,
    ) -> ProviderActionResult:
        """Discover an active provider session if one exists."""


@dataclass(slots=True)
class ProviderSessionResult:
    """Structured response describing a provider session to start/resume."""

    session_id: str
    command: List[str]
    cwd: Optional[Path] = None
    env: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("provider session result must include session_id")
        if not isinstance(self.command, list) or not self.command:
            raise ValueError("provider session result must include command list")

    @property
    def environment(self) -> Dict[str, str]:
        return self.env or {}

    @property
    def extra_metadata(self) -> Dict[str, Any]:
        return self.metadata or {}
