"""Memory Baseline role spec."""

from aware_environment import RoleSpec

MEMORY_BASELINE = RoleSpec(
    slug="memory-baseline",
    title="Memory Baseline",
    description="Foundational working/episodic memory policies for all Aware agents.",
    policy_ids=(
        "02-agent-01-identity",
        "04-agent-01-memory-hierarchy",
    ),
)

__all__ = ["MEMORY_BASELINE"]
