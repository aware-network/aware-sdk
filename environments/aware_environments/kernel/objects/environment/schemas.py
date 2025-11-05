from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class RenderAgentPayload(BaseModel):
    model_config = ConfigDict(ser_json_tostr=True)
    markdown: str
    output_path: Optional[Path] = Field(default=None)
    agent: str
    process: Optional[str] = None
    thread: Optional[str] = None
    mode: str = "stdout"
    version_metadata: Dict[str, Any] = Field(default_factory=dict)
    session_snapshot: Dict[str, Any] = Field(default_factory=dict)
    inspected_receipts: List[Dict[str, Any]] = Field(default_factory=list)
    workspace_paths: Dict[str, str] = Field(default_factory=dict)
    include_constitution: bool = True


class RenderRolePayload(BaseModel):
    model_config = ConfigDict(ser_json_tostr=True)
    markdown: str
    output_path: Optional[Path] = Field(default=None)


class RenderRulePayload(BaseModel):
    model_config = ConfigDict(ser_json_tostr=True)
    markdown: str
    output_path: Optional[Path] = Field(default=None)
    fragments_receipt: Dict[str, object] | None = Field(default=None)


class RenderObjectPayload(BaseModel):
    model_config = ConfigDict(ser_json_tostr=True)
    markdown: str
    object: str
    output_path: Optional[Path] = Field(default=None)
    mode: str = "stdout"


class RenderProtocolPayload(BaseModel):
    model_config = ConfigDict(ser_json_tostr=True)
    markdown: str
    output_path: Optional[Path] = Field(default=None)
    protocols: List[str] = Field(default_factory=list)


class RenderGuidePayload(BaseModel):
    model_config = ConfigDict(ser_json_tostr=True)
    markdown: str
    output_path: Optional[Path] = None
    written_paths: list[Path] = Field(default_factory=list)
    guide_outputs: Dict[str, object] = Field(default_factory=dict)


class EnvironmentLockPayload(BaseModel):
    model_config = ConfigDict(ser_json_tostr=True)
    lock: Dict[str, Any]
    output_path: Optional[Path] = None
    written_paths: List[Path] = Field(default_factory=list)


class RulesLockPayload(BaseModel):
    model_config = ConfigDict(ser_json_tostr=True)
    lock: Dict[str, Any]
    output_path: Optional[Path] = None
    written_paths: List[Path] = Field(default_factory=list)


class DescribeEnvironmentPayload(BaseModel):
    title: str
    constitution_rule: Optional[str] = None
    constitution_rule_title: Optional[str] = None
    agent_count: int
    role_count: int
    rule_count: int
    object_count: int
    agents: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    rules: List[str] = Field(default_factory=list)
    objects: List[str] = Field(default_factory=list)


class ApplyPatchPayload(BaseModel):
    model_config = ConfigDict(ser_json_tostr=True)
    path: Path
    status: str
    summary: str
    diff_hash: Optional[str] = None
    mode: str = "plan"


__all__ = [
    "RenderAgentPayload",
    "RenderRolePayload",
    "RenderRulePayload",
    "RenderObjectPayload",
    "RenderProtocolPayload",
    "RenderGuidePayload",
    "EnvironmentLockPayload",
    "RulesLockPayload",
    "DescribeEnvironmentPayload",
    "ApplyPatchPayload",
]
