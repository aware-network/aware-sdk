from __future__ import annotations

from pathlib import Path

from ..core.config import ToolConfig
from ..core.util import run, CmdResult


class SystemdManager:
    def __init__(self, cfg: ToolConfig):
        self.cfg = cfg

    def tmux_unit_path(self) -> Path:
        return self.cfg.systemd_user_dir / "tmux.service"

    def write_tmux_unit(self, tmux_path: str | None = None) -> Path:
        self.cfg.systemd_user_dir.mkdir(parents=True, exist_ok=True)
        unit = self.tmux_unit_path()
        tmux_exec = tmux_path or "/usr/bin/tmux"
        unit.write_text(
            (
                "[Unit]\n"
                "Description=tmux server\n\n"
                "[Service]\n"
                "Type=oneshot\n"
                f"ExecStart={tmux_exec} start-server\n"
                f"ExecStop={tmux_exec} kill-server\n"
                "RemainAfterExit=yes\n"
                "Restart=on-failure\n\n"
                "[Install]\n"
                "WantedBy=default.target\n"
            )
        )
        return unit

    def daemon_reload(self) -> CmdResult:
        return run(["bash", "-lc", "systemctl --user daemon-reload"], check=False)

    def enable_tmux_unit(self) -> CmdResult:
        return run(["bash", "-lc", "systemctl --user enable --now tmux.service"], check=False)

    def is_unit_enabled(self) -> bool:
        res = run(["bash", "-lc", "systemctl --user is-enabled tmux.service"], check=False)
        return res.code == 0 and res.out.strip() == "enabled"

    def is_unit_active(self) -> bool:
        res = run(["bash", "-lc", "systemctl --user is-active tmux.service"], check=False)
        return res.code == 0 and res.out.strip() == "active"

    def enable_linger(self, user: str) -> CmdResult:
        return run(["bash", "-lc", f"loginctl enable-linger {user} || true"], check=False)
