from __future__ import annotations

from typing import List

from aware_terminal.bootstrap.tmux_service import TmuxServiceOrchestrator
from aware_terminal.doctor.context import DoctorContext
from aware_terminal.doctor.models import (
    DoctorCheckResult,
    DoctorMessage,
    DoctorMessageLevel,
    DoctorRemediation,
    DoctorStatus,
)


def run_tmux_check(context: DoctorContext) -> DoctorCheckResult:
    orchestrator = TmuxServiceOrchestrator(context.config)
    caps = orchestrator.detect_capabilities()

    messages: List[DoctorMessage] = []
    remediations: List[DoctorRemediation] = []
    status = DoctorStatus.OK
    blocking = False

    if not caps.has_tmux:
        messages.append(DoctorMessage(level=DoctorMessageLevel.ERROR, text="tmux binary not found"))
        remediations.append(
            DoctorRemediation(
                summary="Install tmux",
                command=["sudo", "apt", "install", "tmux"],
            )
        )
        return DoctorCheckResult(
            slug="tmux",
            title="tmux service",
            status=DoctorStatus.ERROR,
            summary="tmux binary missing",
            messages=messages,
            remediations=remediations,
            data=caps.__dict__,
            blocking=True,
        )

    if caps.systemd_available:
        messages.append(DoctorMessage(level=DoctorMessageLevel.INFO, text="systemd user services available"))
        if caps.unit_enabled and caps.unit_active:
            messages.append(DoctorMessage(level=DoctorMessageLevel.SUCCESS, text="tmux.service enabled and active"))
        else:
            if not caps.unit_exists:
                messages.append(
                    DoctorMessage(
                        level=DoctorMessageLevel.WARNING,
                        text="tmux systemd unit not present",
                    )
                )
            if not caps.unit_enabled:
                messages.append(
                    DoctorMessage(
                        level=DoctorMessageLevel.ERROR,
                        text="tmux.service not enabled",
                    )
                )
            if not caps.unit_active:
                messages.append(
                    DoctorMessage(
                        level=DoctorMessageLevel.ERROR,
                        text="tmux.service not active",
                    )
                )
            remediations.append(
                DoctorRemediation(
                    summary="Enable tmux systemd user service",
                    command=["systemctl", "--user", "enable", "--now", "tmux.service"],
                )
            )
            status = DoctorStatus.ERROR
            blocking = True
    else:
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.INFO,
                text="systemd user services unavailable; relying on direct tmux server",
            )
        )
        if caps.server_running:
            messages.append(DoctorMessage(level=DoctorMessageLevel.SUCCESS, text="tmux server running"))
        else:
            messages.append(DoctorMessage(level=DoctorMessageLevel.ERROR, text="tmux server not running"))
            remediations.append(
                DoctorRemediation(
                    summary="Start tmux server",
                    command=["tmux", "start-server"],
                )
            )
            status = DoctorStatus.ERROR
            blocking = True

    return DoctorCheckResult(
        slug="tmux",
        title="tmux service",
        status=status,
        summary="tmux service status",
        messages=messages,
        remediations=remediations,
        data=caps.__dict__,
        blocking=blocking,
    )
