"""Typed receipt schema for filesystem operation plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from ..exceptions import AwareEnvironmentError


SCHEMA_VERSION = "aware.fs.receipt/v1"


@dataclass(frozen=True)
class OperationContext:
    object_type: str
    function: str
    selectors: dict[str, str]


@dataclass(frozen=True)
class EnsureOp:
    type: Literal["ensure"] = "ensure"
    path: Path = field(default_factory=Path)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MoveOp:
    type: Literal["move"] = "move"
    src: Path = field(default_factory=Path)
    dest: Path = field(default_factory=Path)
    overwrite: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class WriteOp:
    type: Literal["write"] = "write"
    path: Path = field(default_factory=Path)
    event: Literal["created", "updated", "appended"] = "updated"
    policy: str = "modifiable"
    doc_type: str = ""
    content_hash: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    hook_metadata: dict[str, object] = field(default_factory=dict)
    timestamp: datetime | None = None


FsOp = EnsureOp | MoveOp | WriteOp


@dataclass(frozen=True)
class PolicyDecision:
    path: Path
    action: Literal["guard_create", "guard_append", "guard_modify"]
    policy: str
    result: Literal["allow", "deny"]
    message: str | None = None


@dataclass(frozen=True)
class HookLog:
    name: str
    path: Path | None
    status: Literal["invoked", "skipped", "failed"]
    error: str | None = None


@dataclass(frozen=True)
class Receipt:
    """Structured receipt for a single plan application."""

    receipt_id: str
    timestamp: datetime
    context: OperationContext
    fs_ops: list[FsOp] = field(default_factory=list)
    policy_decisions: list[PolicyDecision] = field(default_factory=list)
    hooks: list[HookLog] = field(default_factory=list)
    schema: str = SCHEMA_VERSION

    def add_fs_op(self, op: FsOp) -> None:
        self.fs_ops.append(op)

    def add_policy_decision(self, decision: PolicyDecision) -> None:
        self.policy_decisions.append(decision)

    def add_hook_log(self, log: HookLog) -> None:
        self.hooks.append(log)

    def ensure_schema(self) -> None:
        if self.schema != SCHEMA_VERSION:
            raise AwareEnvironmentError(
                f"Unknown receipt schema '{self.schema}'. Expected '{SCHEMA_VERSION}'."
            )
