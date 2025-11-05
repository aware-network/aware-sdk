"""Typed models for terminal descriptors and related payloads."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field

from aware_terminal_providers.core.descriptor import ProviderDescriptorModel


class TerminalDescriptorModel(BaseModel):
    """Schema for terminal descriptors stored under .aware/threads/<thread>/terminals/."""

    id: str
    thread_id: str
    name: str
    cwd: Path
    shell: str = "/bin/bash"
    env: Dict[str, str] = Field(default_factory=dict)
    session_id: Optional[str] = None
    tmux_window: Optional[str] = None
    provider: Optional[ProviderDescriptorModel] = None
    apt_id: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_attached_at: Optional[datetime] = None

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


__all__ = ["TerminalDescriptorModel"]
