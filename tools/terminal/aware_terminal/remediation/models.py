from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence

from pydantic import BaseModel, Field

from aware_terminal.core.config import ToolConfig

if TYPE_CHECKING:
    from .rendering.renderer import RemediationRenderer

class RemediationStatus(str, Enum):
    EXECUTED = "executed"
    MANUAL = "manual"
    FAILED = "failed"
    SKIPPED = "skipped"


class RemediationPolicy(str, Enum):
    APPLY = "apply"
    SKIP = "skip"
    PROMPT = "prompt"


class CapabilitySnapshot(BaseModel):
    summary: str
    data: Dict[str, Any] = Field(default_factory=dict)


class RemediationOutcome(BaseModel):
    action_id: str
    summary: str
    status: RemediationStatus
    blocking: bool = False
    command: Optional[Sequence[str]] = None
    message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def as_manual(self) -> bool:
        return self.status in {RemediationStatus.MANUAL, RemediationStatus.FAILED}


class RemediationAction:
    """Base class for setup/doctor remediation actions."""

    id: str
    summary: str
    blocking: bool = True
    policy: RemediationPolicy = RemediationPolicy.APPLY
    platforms: Iterable[str] = ("linux",)

    def supports_platform(self, platform: str) -> bool:
        if not self.platforms:
            return True
        return platform in self.platforms

    def capability(self, context: "RemediationContext") -> CapabilitySnapshot:
        raise NotImplementedError

    def run(
        self,
        context: "RemediationContext",
        renderer: "RemediationRenderer | None" = None,
    ) -> RemediationOutcome:
        raise NotImplementedError


@dataclass
class RemediationContext:
    config: ToolConfig
    auto: bool
    platform: str
    provider_policy: RemediationPolicy
    state: Optional["SetupState"] = None
    interactive: bool = False
    interactive: bool = False


class SetupRun(BaseModel):
    action_id: str
    status: RemediationStatus
    timestamp: datetime
    details: Dict[str, Any] = Field(default_factory=dict)


class SetupState(BaseModel):
    version: int = 1
    runs: List[SetupRun] = Field(default_factory=list)
    manifests_refreshed_at: Optional[datetime] = None

    def record(self, outcome: RemediationOutcome) -> None:
        existing = [run for run in self.runs if run.action_id == outcome.action_id]
        for run in existing:
            self.runs.remove(run)
        details = dict(outcome.details)
        if outcome.message and "message" not in details:
            details["message"] = outcome.message
        if outcome.command and "command" not in details:
            details["command"] = list(outcome.command)
        self.runs.append(
            SetupRun(
                action_id=outcome.action_id,
                status=outcome.status,
                timestamp=outcome.timestamp,
                details=details,
            )
        )

    def last_status(self, action_id: str) -> Optional[SetupRun]:
        for run in reversed(self.runs):
            if run.action_id == action_id:
                return run
        return None
