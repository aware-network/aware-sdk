"""Project/Task Baseline role spec."""

from aware_environment import RoleSpec

PROJECT_TASK_BASELINE = RoleSpec(
    slug="project-task-baseline",
    title="Project/Task Baseline",
    description="Core task lifecycle rules covering analysis, design, implementation, and change tracking.",
    policy_ids=(
        "02-task-01-lifecycle",
        "02-task-03-change-tracking",
    ),
)

__all__ = ["PROJECT_TASK_BASELINE"]
