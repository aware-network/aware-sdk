from __future__ import annotations

from typing import List

from aware_terminal.core.config import ToolConfig
from aware_terminal.core.env import EnvironmentInspector
from aware_terminal.doctor.checks import (
    run_environment_check,
    run_gnome_check,
    run_provider_check,
    run_terminal_check,
    run_tmux_check,
)
from aware_terminal.doctor.context import DoctorContext
from aware_terminal.doctor.models import DoctorCheckResult, DoctorReport, ProviderAction


def run_doctor(*, config: ToolConfig | None = None) -> DoctorReport:
    cfg = config or ToolConfig()
    inspector = EnvironmentInspector()
    context = DoctorContext(config=cfg, inspector=inspector)

    checks: List[DoctorCheckResult] = []
    provider_actions: List[ProviderAction]

    environment_result = run_environment_check(context)
    checks.append(environment_result)

    provider_result, provider_actions = run_provider_check(context)
    checks.append(provider_result)

    terminal_result = run_terminal_check(context)
    gnome_result = run_gnome_check(context)
    tmux_result = run_tmux_check(context)
    checks.extend([terminal_result, gnome_result, tmux_result])

    session_type = environment_result.data.get("session_type") or inspector.session_type()

    return DoctorReport(
        session_type=session_type,
        checks=checks,
        provider_actions=provider_actions,
    )
