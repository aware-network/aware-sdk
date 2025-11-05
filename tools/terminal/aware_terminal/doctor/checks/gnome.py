from __future__ import annotations

from typing import List

from aware_terminal.bootstrap.window_manager.gnome import GnomeWindowPlacementManager
from aware_terminal.core.util import run
from aware_terminal.doctor.context import DoctorContext
from aware_terminal.doctor.models import (
    DoctorCheckResult,
    DoctorMessage,
    DoctorMessageLevel,
    DoctorRemediation,
    DoctorStatus,
    combine_status,
)


def _read_disable_user_extensions() -> str:
    result = run(["bash", "-lc", "gsettings get org.gnome.shell disable-user-extensions"], check=False)
    return result.out.strip()


def run_gnome_check(context: DoctorContext) -> DoctorCheckResult:
    has_gnome = context.inspector.has_gnome()
    messages: List[DoctorMessage] = []
    remediations: List[DoctorRemediation] = []
    status = DoctorStatus.OK
    summary = "GNOME Auto Move Windows extension status"

    if not has_gnome:
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.WARNING,
                text="GNOME shell not detected; skip auto-move extension checks.",
            )
        )
        return DoctorCheckResult(
            slug="gnome",
            title="GNOME Auto Move Windows",
            status=DoctorStatus.WARNING,
            summary="GNOME shell tooling unavailable",
            messages=messages,
            data={"available": False},
        )

    manager = GnomeWindowPlacementManager(context.config)
    caps = manager.capabilities()
    cli_caps = caps.get("cli", {})
    ext_caps = caps.get("extension", {})
    rules_caps = caps.get("rules", {})

    has_cli = bool(cli_caps.get("available", False))
    installed = bool(ext_caps.get("installed", False))
    enabled = bool(ext_caps.get("enabled", False))
    requires_reload = bool(ext_caps.get("requires_reload", False))
    install_detail = ext_caps.get("install_source_detail") or ext_caps.get("install_source")
    rules_count = int(rules_caps.get("count", 0))

    messages.append(
        DoctorMessage(
            level=DoctorMessageLevel.INFO,
            text=f"gnome-extensions CLI available: {has_cli}",
        )
    )

    if installed:
        detail_note = f" ({install_detail})" if install_detail else ""
        messages.append(
            DoctorMessage(level=DoctorMessageLevel.SUCCESS, text=f"Auto Move Windows extension installed{detail_note}")
        )
    else:
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.ERROR,
                text="Auto Move Windows extension missing",
            )
        )
        status = combine_status(status, DoctorStatus.ERROR)
        remediations.append(
            DoctorRemediation(
                summary="Install and enable GNOME Auto Move Windows extension",
                command=["uv", "run", "aware-terminal", "gnome", "fix"],
            )
        )

    if installed and enabled:
        messages.append(DoctorMessage(level=DoctorMessageLevel.SUCCESS, text="Extension enabled"))
    elif installed:
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.WARNING,
                text="Extension installed but not enabled",
            )
        )
        status = combine_status(status, DoctorStatus.WARNING)
        remediations.append(
            DoctorRemediation(
                summary="Enable Auto Move Windows extension",
                command=["uv", "run", "aware-terminal", "gnome", "fix"],
            )
        )
    else:
        status = combine_status(status, DoctorStatus.ERROR)

    if requires_reload:
        hint = ext_caps.get("reload_hint") or "Reload GNOME Shell to finish applying the extension."
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.WARNING,
                text=f"Extension changes pending GNOME Shell reload — {hint}",
            )
        )

    disable_flag = _read_disable_user_extensions()
    messages.append(
        DoctorMessage(
            level=DoctorMessageLevel.INFO,
            text=f"disable-user-extensions: {disable_flag}",
        )
    )
    if disable_flag.lower() == "true":
        status = combine_status(status, DoctorStatus.WARNING)
        remediations.append(
            DoctorRemediation(
                summary="Allow user GNOME extensions",
                command=[
                    "bash",
                    "-lc",
                    "gsettings set org.gnome.shell disable-user-extensions false",
                ],
            )
        )

    if rules_count:
        preview_entries = rules_caps.get("preview") or []
        preview = ", ".join(preview_entries)
        source = rules_caps.get("source")
        source_note = f" via {source}" if source and source != "none" else ""
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.SUCCESS,
                text=f"Auto-move rules configured ({rules_count} entries{source_note}{f', sample: {preview}' if preview else ''})",
            )
        )
    else:
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.WARNING,
                text="Auto-move rules empty — run setup to seed workspace assignments.",
            )
        )
        status = combine_status(status, DoctorStatus.WARNING)
        remediations.append(
            DoctorRemediation(
                summary="Populate GNOME auto-move rules",
                command=["uv", "run", "aware-terminal", "setup"],
            )
        )

    blocking = installed is False or (installed and not enabled)

    return DoctorCheckResult(
        slug="gnome",
        title="GNOME Auto Move Windows",
        status=status,
        summary=summary,
        blocking=blocking,
        messages=messages,
        remediations=remediations,
        data={
            "capabilities": caps,
            "disable_user_extensions": disable_flag,
            "requires_reload": requires_reload,
        },
    )
