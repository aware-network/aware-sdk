from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, computed_field


class DoctorStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class DoctorMessageLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class DoctorMessage(BaseModel):
    level: DoctorMessageLevel
    text: str


class DoctorRemediation(BaseModel):
    summary: str
    command: Optional[List[str]] = None
    docs_url: Optional[str] = None


class ProviderActionStatus(str, Enum):
    INSTALLED = "installed"
    MISSING = "missing"
    UPDATE_AVAILABLE = "update_available"
    PENDING = "pending"


class ProviderAction(BaseModel):
    slug: str
    title: str
    status: ProviderActionStatus
    summary: str
    cli_name: Optional[str] = None
    package: Optional[str] = None
    install_command: Optional[List[str]] = None
    fallback_command: Optional[List[str]] = None
    installed_version: Optional[str] = None
    latest_version: Optional[str] = None
    docs_url: Optional[str] = None
    auto_install_env: Optional[str] = None


class DoctorCheckResult(BaseModel):
    slug: str
    title: str
    status: DoctorStatus
    summary: str
    messages: List[DoctorMessage] = Field(default_factory=list)
    remediations: List[DoctorRemediation] = Field(default_factory=list)
    data: Dict[str, Any] = Field(default_factory=dict)
    blocking: bool = False


STATUS_PRIORITY: Dict[DoctorStatus, int] = {
    DoctorStatus.OK: 0,
    DoctorStatus.WARNING: 1,
    DoctorStatus.ERROR: 2,
}


def combine_status(current: DoctorStatus, new: DoctorStatus) -> DoctorStatus:
    return new if STATUS_PRIORITY[new] > STATUS_PRIORITY[current] else current


class DoctorReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_type: Optional[str] = None
    checks: List[DoctorCheckResult] = Field(default_factory=list)
    provider_actions: List[ProviderAction] = Field(default_factory=list)

    @computed_field  # type: ignore[misc]
    @property
    def status(self) -> DoctorStatus:
        overall = DoctorStatus.OK
        for check in self.checks:
            overall = combine_status(overall, check.status)
        return overall

    @computed_field  # type: ignore[misc]
    @property
    def remediations(self) -> List[DoctorRemediation]:
        seen: Dict[str, DoctorRemediation] = {}
        for check in self.checks:
            for remediation in check.remediations:
                key = (remediation.summary, tuple(remediation.command or []))
                if key not in seen:
                    seen[key] = remediation
        return list(seen.values())
