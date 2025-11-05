"""Kernel rule exports."""

from pathlib import Path

from aware_environment import RuleSpec

CURRENT = Path(__file__).parent / "current"
REPO_ROOT = Path(__file__).resolve().parents[4]

RULES = (
    RuleSpec(
        id="00-environment-constitution",
        title="Rule 00 Environment Constitution",
        path=(Path(__file__).parent / "templates" / "00-environment.md").resolve(),
        layer="environment",
        version="0.1",
    ),
    RuleSpec(
        id="01-thread-01-runtime",
        title="Rule 01 Thread Runtime",
        path=(CURRENT / "01-thread.md").resolve(),
        layer="environment",
        version="0.1",
    ),
    RuleSpec(
        id="02-agent-01-identity",
        title="Rule 02 Agent Identity",
        path=(Path(__file__).parent / "templates" / "02-agent.md").resolve(),
        layer="agent",
    ),
    RuleSpec(
        id="02-task-01-lifecycle",
        title="Rule 02 Task Lifecycle",
        path=(CURRENT / "02-task.md").resolve(),
        layer="task",
    ),
    RuleSpec(
        id="02-task-02-status",
        title="Rule 02 Task Status",
        path=(REPO_ROOT / "docs" / "rules" / "02-task" / "02-status.md").resolve(),
        layer="task",
    ),
    RuleSpec(
        id="02-task-03-change-tracking",
        title="Rule 02 Task Change Tracking",
        path=(REPO_ROOT / "docs" / "rules" / "02-task" / "03-change-tracking.md").resolve(),
        layer="task",
    ),
    RuleSpec(
        id="04-agent-01-memory-hierarchy",
        title="Rule 04 Agent Memory Hierarchy",
        path=(CURRENT / "04-agent.md").resolve(),
        layer="agent",
    ),
)

__all__ = ["RULES"]
