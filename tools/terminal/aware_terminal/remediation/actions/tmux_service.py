from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from aware_terminal.bootstrap.tmux_service import TmuxServiceOrchestrator

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


class TmuxServiceAction(RemediationAction):
    id = "tmux_service"
    summary = "tmux systemd service"
    blocking = True
    policy = RemediationPolicy.APPLY
    platforms = ("linux",)

    def __init__(self, context: RemediationContext):
        self.context = context
        self.orchestrator = TmuxServiceOrchestrator(context.config)

    def capability(self, context: RemediationContext) -> CapabilitySnapshot:
        caps = self.orchestrator.detect_capabilities()
        return CapabilitySnapshot(summary="tmux service capabilities", data=asdict(caps))

    def run(
        self,
        context: RemediationContext,
        renderer=None,
    ) -> RemediationOutcome:
        result = self.orchestrator.ensure_service_ready(auto=context.auto)
        status = STATUS_MAP.get(result.status, RemediationStatus.MANUAL)
        command: Optional[list[str]] = None
        for action in result.actions:
            if action.command:
                command = action.command
                break
        actions_payload = [
            {
                "summary": action.summary,
                "status": action.status,
                "command": action.command,
                "message": action.message,
            }
            for action in result.actions
        ]
        message = result.error
        if not message:
            for action in result.actions:
                if action.message:
                    message = action.message
                    break
        details = {
            "capabilities": asdict(result.capabilities),
        }
        return RemediationOutcome(
            action_id=self.id,
            summary=self.summary,
            status=status,
            blocking=self.blocking,
            command=command,
            message=message,
            details=details,
            actions=actions_payload,
        )


def TmuxServiceActionFactory(context: RemediationContext):
    return TmuxServiceAction(context)
