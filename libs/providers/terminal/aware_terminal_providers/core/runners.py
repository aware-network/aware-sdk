"\"\"\"Helpers for launching provider processes via aware-terminal.\"\"\""

from __future__ import annotations

from typing import Iterable, Optional
import subprocess


def run_command(command: Iterable[str], *, env: Optional[dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
