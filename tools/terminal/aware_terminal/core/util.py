from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class CmdResult:
    code: int
    out: str
    err: str


def run(cmd: list[str] | str, check: bool = False, env: Optional[dict[str, str]] = None) -> CmdResult:
    is_list = isinstance(cmd, (list, tuple))
    proc = subprocess.run(
        cmd if is_list else (cmd if isinstance(cmd, str) else ""),
        shell=not is_list,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, **(env or {})},
    )
    if check and proc.returncode != 0:
        args_repr = " ".join(shlex.quote(x) for x in cmd) if is_list else (cmd or "")
        raise RuntimeError(f"Command failed ({proc.returncode}): {args_repr}\n{proc.stderr}")
    return CmdResult(code=proc.returncode, out=proc.stdout, err=proc.stderr)


def ensure_dirs(paths: Iterable[Path]) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def which(cmd: str) -> Optional[str]:
    res = run(["bash", "-lc", f"command -v {shlex.quote(cmd)} || true"])
    return res.out.strip() or None


HOME = Path.home()


def human_ago(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def spawn(cmd: list[str] | str, env: Optional[dict[str, str]] = None) -> None:
    """Start a process without waiting (non-blocking)."""
    is_list = isinstance(cmd, (list, tuple))
    try:
        subprocess.Popen(
            cmd if is_list else (cmd if isinstance(cmd, str) else ""),
            shell=not is_list,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env={**os.environ, **(env or {})},
            start_new_session=True,
        )
    except Exception:
        # Best-effort; ignore spawn errors in UI contexts
        pass


def log_append(filename: str, message: str) -> None:
    try:
        logdir = HOME / ".aware" / "terminal" / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        with (logdir / filename).open("a") as f:
            f.write(message + "\n")
    except Exception:
        pass
