"""Kernel agent exports."""

from .desktop_manager import DESKTOP_MANAGER_AGENT
from .aware_manager import AWARE_MANAGER_AGENT

AGENTS = (
    DESKTOP_MANAGER_AGENT,
    AWARE_MANAGER_AGENT,
)

__all__ = [
    "AGENTS",
    "DESKTOP_MANAGER_AGENT",
    "AWARE_MANAGER_AGENT",
]
