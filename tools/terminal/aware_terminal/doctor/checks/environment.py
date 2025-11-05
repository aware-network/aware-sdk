from __future__ import annotations

from aware_terminal.doctor.context import DoctorContext
from aware_terminal.doctor.models import (
    DoctorCheckResult,
    DoctorMessage,
    DoctorMessageLevel,
    DoctorStatus,
)


def run_environment_check(context: DoctorContext) -> DoctorCheckResult:
    session_type = context.inspector.session_type()
    has_gnome = context.inspector.has_gnome()

    messages = [
        DoctorMessage(level=DoctorMessageLevel.INFO, text=f"Session type: {session_type}"),
    ]

    status = DoctorStatus.OK
    summary = f"Running on {session_type}"

    if has_gnome:
        messages.append(
            DoctorMessage(level=DoctorMessageLevel.SUCCESS, text="GNOME shell detected (gsettings available)")
        )
    else:
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.WARNING,
                text="GNOME shell tooling not detected—GNOME Auto Move checks may be skipped.",
            )
        )
        status = DoctorStatus.WARNING
        summary = f"{summary} without GNOME shell support"

    return DoctorCheckResult(
        slug="environment",
        title="Desktop Environment",
        status=status,
        summary=summary,
        messages=messages,
        data={
            "session_type": session_type,
            "has_gnome": has_gnome,
        },
    )
