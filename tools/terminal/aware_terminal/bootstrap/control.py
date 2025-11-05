from __future__ import annotations

from dataclasses import dataclass

from ..core.util import run

SESSION_NAME = "aware-control"
WINDOW_DASHBOARD = "dashboard"
WINDOW_DOCS = "docs"


@dataclass
class ControlSessionResult:
    created: bool
    session: str = SESSION_NAME


def ensure_control_session(command: str = "aware-terminal control --provider cli") -> ControlSessionResult:
    ls = run(["tmux", "has-session", "-t", SESSION_NAME], check=False)
    created = ls.code != 0

    if created:
        run(["tmux", "new-session", "-ds", SESSION_NAME, "bash", "-lc", command], check=False)
        run(["tmux", "rename-window", "-t", f"{SESSION_NAME}:0", WINDOW_DASHBOARD], check=False)
        run(["tmux", "new-window", "-t", SESSION_NAME, "-n", WINDOW_DOCS, "bash"], check=False)
    else:
        run([
            "tmux",
            "respawn-window",
            "-k",
            "-t",
            f"{SESSION_NAME}:{WINDOW_DASHBOARD}",
            "bash",
            "-lc",
            command,
        ], check=False)

    return ControlSessionResult(created=created)
