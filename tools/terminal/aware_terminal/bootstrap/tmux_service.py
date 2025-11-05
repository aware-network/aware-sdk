from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..core.config import ToolConfig
from ..core.env import EnvironmentInspector
from ..core.util import run
from .tmux import TmuxManager
from .systemd import SystemdManager


@dataclass
class ServiceCapabilities:
    tmux_path: Optional[str]
    has_tmux: bool
    systemd_available: bool
    unit_exists: bool
    unit_enabled: bool
    unit_active: bool
    server_running: bool


@dataclass
class ServiceActionResult:
    summary: str
    status: str  # executed | failed | manual
    command: Optional[List[str]] = None
    message: Optional[str] = None


@dataclass
class TmuxServiceResult:
    status: str  # success | failed | manual
    capabilities: ServiceCapabilities
    actions: List[ServiceActionResult] = field(default_factory=list)
    error: Optional[str] = None


class TmuxServiceOrchestrator:
    def __init__(self, cfg: ToolConfig):
        self.cfg = cfg
        self.tmux = TmuxManager(cfg)
        self.systemd = SystemdManager(cfg)

    # Capability detection -------------------------------------------------
    def detect_capabilities(self) -> ServiceCapabilities:
        tmux_path = self.tmux.resolve_tmux_path()
        has_tmux = tmux_path is not None
        systemd_available = self._systemd_available()
        unit_path = self.systemd.tmux_unit_path()
        unit_exists = unit_path.exists()
        unit_enabled = False
        unit_active = False
        if systemd_available:
            unit_enabled = self.systemd.is_unit_enabled()
            unit_active = self.systemd.is_unit_active()
        server_running = self.tmux.is_server_running()
        return ServiceCapabilities(
            tmux_path=tmux_path,
            has_tmux=has_tmux,
            systemd_available=systemd_available,
            unit_exists=unit_exists,
            unit_enabled=unit_enabled,
            unit_active=unit_active,
            server_running=server_running,
        )

    def ensure_service_ready(self, *, auto: bool) -> TmuxServiceResult:
        caps = self.detect_capabilities()
        actions: List[ServiceActionResult] = []

        if not caps.has_tmux:
            actions.append(
                ServiceActionResult(
                    summary="Install tmux",
                    status="manual",
                    command=["sudo", "apt", "install", "tmux"],
                )
            )
            return TmuxServiceResult(status="manual", capabilities=caps, actions=actions,
                                     error="tmux binary not found")

        if not auto:
            # Surface instructions only
            return self._manual_instructions(caps)

        if caps.systemd_available:
            return self._ensure_with_systemd(caps)

        return self._ensure_without_systemd(caps)

    # Internal helpers -----------------------------------------------------
    def _manual_instructions(self, caps: ServiceCapabilities) -> TmuxServiceResult:
        actions: List[ServiceActionResult] = []
        if caps.systemd_available:
            actions.append(
                ServiceActionResult(
                    summary="Enable tmux systemd service",
                    status="manual",
                    command=["systemctl", "--user", "enable", "--now", "tmux.service"],
                )
            )
        else:
            actions.append(
                ServiceActionResult(
                    summary="Start tmux server",
                    status="manual",
                    command=["tmux", "start-server"],
                )
            )
        return TmuxServiceResult(status="manual", capabilities=caps, actions=actions)

    def _ensure_with_systemd(self, caps: ServiceCapabilities) -> TmuxServiceResult:
        actions: List[ServiceActionResult] = []
        tmux_path = caps.tmux_path or "/usr/bin/tmux"

        if not caps.unit_exists:
            self.systemd.write_tmux_unit(tmux_path)
            actions.append(ServiceActionResult(summary="Wrote tmux systemd unit", status="executed"))

        reload_res = self.systemd.daemon_reload()
        reload_status = "executed" if reload_res.code == 0 else "manual"
        reload_message = reload_res.err.strip() or reload_res.out.strip() or None
        actions.append(
            ServiceActionResult(
                summary="Reloaded systemd user daemon",
                status=reload_status,
                message=reload_message,
                command=["systemctl", "--user", "daemon-reload"] if reload_res.code != 0 else None,
            )
        )
        if reload_res.code != 0:
            # Do not attempt enable; report manual action
            caps = self.detect_capabilities()
            return TmuxServiceResult(status="manual", capabilities=caps, actions=actions,
                                     error=reload_res.err or reload_res.out)

        enable_res = self.systemd.enable_tmux_unit()
        enable_status = "executed" if enable_res.code == 0 else "manual"
        enable_message = enable_res.err.strip() or enable_res.out.strip() or None
        actions.append(
            ServiceActionResult(
                summary="Enabled tmux systemd service",
                status=enable_status,
                message=enable_message,
                command=["systemctl", "--user", "enable", "--now", "tmux.service"]
                if enable_res.code != 0 else None,
            )
        )
        if enable_res.code != 0:
            caps = self.detect_capabilities()
            return TmuxServiceResult(status="manual", capabilities=caps, actions=actions,
                                     error=enable_res.err or enable_res.out)

        # Enable linger best effort
        user = EnvironmentInspector().user()
        linger_res = self.systemd.enable_linger(user)
        actions.append(
            ServiceActionResult(
                summary="Enabled user linger",
                status="executed" if linger_res.code == 0 else "failed",
                message=linger_res.err.strip() or linger_res.out.strip() or None,
                command=["loginctl", "enable-linger", user],
            )
        )

        caps = self.detect_capabilities()
        return TmuxServiceResult(status="success", capabilities=caps, actions=actions)

    def _ensure_without_systemd(self, caps: ServiceCapabilities) -> TmuxServiceResult:
        actions: List[ServiceActionResult] = []
        if not caps.server_running:
            start_res = self.tmux.start_server()
            if start_res:
                actions.append(ServiceActionResult(summary="Started tmux server", status="executed"))
                caps = self.detect_capabilities()
                return TmuxServiceResult(status="success", capabilities=caps, actions=actions)
            actions.append(
                ServiceActionResult(
                    summary="Start tmux server",
                    status="manual",
                    command=["tmux", "start-server"],
                    message="tmux start-server failed",
                )
            )
            return TmuxServiceResult(status="manual", capabilities=caps, actions=actions,
                                     error="tmux start-server failed")

        caps = self.detect_capabilities()
        return TmuxServiceResult(status="success", capabilities=caps, actions=actions)

    def _systemd_available(self) -> bool:
        check = run(["bash", "-lc", "command -v systemctl >/dev/null 2>&1 && echo yes || echo no"], check=False)
        if check.out.strip() != "yes":
            return False
        probe = run(["bash", "-lc", "systemctl --user show-environment >/dev/null 2>&1"], check=False)
        if probe.code != 0 and "Failed to connect" in (probe.err or ""):
            return False
        return True
