"""Thread orchestration role spec."""

from aware_environment import RoleSpec

THREAD_ORCHESTRATION = RoleSpec(
    slug="thread-orchestration",
    title="Thread Orchestration",
    description="Operates thread runtime controls (status, branches, participants) via CLI-first flow.",
    policy_ids=(
        "01-thread-01-runtime",
    ),
    protocol_ids=(
        "thread-apt-binding",
    ),
)

__all__ = ["THREAD_ORCHESTRATION"]
