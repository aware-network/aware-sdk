from __future__ import annotations

from aware_terminal.bootstrap.window_manager.gnome import GnomeWindowPlacementManager
from aware_terminal.core.env import EnvironmentInspector

from ..models import (
    CapabilitySnapshot,
    RemediationAction,
    RemediationContext,
    RemediationOutcome,
    RemediationPolicy,
    RemediationStatus,
)


STATUS_MAP = {
    "success": RemediationStatus.EXECUTED,
    "manual": RemediationStatus.MANUAL,
    "failed": RemediationStatus.FAILED,
}


class GnomeWindowAction(RemediationAction):
    id = "gnome_window"
    summary = "GNOME Auto Move Windows"
    blocking = True
    policy = RemediationPolicy.APPLY
    platforms = ("linux",)

    def __init__(self, context: RemediationContext):
        self.context = context
        self.manager = GnomeWindowPlacementManager(context.config)

    def capability(self, context: RemediationContext) -> CapabilitySnapshot:
        caps = self.manager.capabilities()
        return CapabilitySnapshot(summary="GNOME capabilities", data=caps)

    def run(
        self,
        context: RemediationContext,
        renderer=None,
    ) -> RemediationOutcome:
        result = self.manager.ensure_ready(auto=context.auto)
        status = STATUS_MAP.get(result.status, RemediationStatus.MANUAL)
        details = result.data or {}
        outcome = RemediationOutcome(
            action_id=self.id,
            summary=self.summary,
            status=status,
            blocking=self.blocking,
            command=result.command,
            message=result.message,
            details=details,
        )
        return outcome


def GnomeWindowActionFactory(context: RemediationContext):
    # Only applicable when GNOME is detected (session type gnome shell).
    if context.platform != "linux":
        return None
    if not EnvironmentInspector().has_gnome():
        return None
    return GnomeWindowAction(context)
