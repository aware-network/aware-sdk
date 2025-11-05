"""Desktop Manager agent spec."""

from aware_environment import AgentSpec

DESKTOP_MANAGER_AGENT = AgentSpec(
    slug="desktop-manager",
    title="Desktop Manager",
    role_slugs=(
        "memory-baseline",
        "project-task-baseline",
        "thread-orchestration",
    ),
    description="Desktop manager agent coordinating CLI workflows and kernel bindings.",
)

__all__ = ["DESKTOP_MANAGER_AGENT"]
