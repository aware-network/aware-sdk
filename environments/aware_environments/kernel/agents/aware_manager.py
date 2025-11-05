"""Aware Manager agent spec."""

from aware_environment import AgentSpec

AWARE_MANAGER_AGENT = AgentSpec(
    slug="aware-manager",
    title="Aware Manager",
    role_slugs=(
        "memory-baseline",
        "project-task-baseline",
        "thread-orchestration",
    ),
    description="Orchestrator manager agent coordinating process/thread bindings and receipts.",
)

__all__ = ["AWARE_MANAGER_AGENT"]
