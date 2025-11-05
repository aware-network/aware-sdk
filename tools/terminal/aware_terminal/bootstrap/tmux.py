from __future__ import annotations

from pathlib import Path

from ..core.config import ToolConfig
from ..core.util import HOME, ensure_dirs, run

TPM_REPO = "https://github.com/tmux-plugins/tpm"
RESURRECT_REPO = "https://github.com/tmux-plugins/tmux-resurrect"
CONTINUUM_REPO = "https://github.com/tmux-plugins/tmux-continuum"


class TmuxManager:
    def __init__(self, cfg: ToolConfig):
        self.cfg = cfg

    def resolve_tmux_path(self) -> str | None:
        res = run(["bash", "-lc", "command -v tmux || true"], check=False)
        path = res.out.strip()
        return path or None

    def ensure_installed(self) -> None:
        run(["bash", "-lc", "sudo apt update && sudo apt install -y tmux git"], check=False)

    def write_conf(self) -> None:
        content = (
            "set -g mouse on\n"
            "set -g history-limit 100000\n"
            "set -g renumber-windows on\n\n"
            "# Keep panes visible after exit to avoid accidental session loss\n"
            "set -g remain-on-exit on\n"
            "set -g exit-empty off\n\n"
            "# Be conservative about destroying windows/sessions\n"
            "set -g destroy-unattached off\n"
            "set -g detach-on-destroy off\n\n"
            "# Friendlier split binds in addition to defaults\n"
            "bind | split-window -h\n"
            "bind - split-window -v\n\n"
            "# TPM\n"
            "set -g @plugin 'tmux-plugins/tpm'\n"
            "set -g @plugin 'tmux-plugins/tmux-resurrect'\n"
            "set -g @plugin 'tmux-plugins/tmux-continuum'\n\n"
            "# Auto save/restore\n"
            "set -g @continuum-restore 'on'\n"
            "set -g @continuum-save-interval '10'\n\n"
            "# Optional: better vim/neovim session handling\n"
            "set -g @resurrect-strategy-nvim 'session'\n"
            "set -g @resurrect-strategy-vim 'session'\n\n"
            "run '~/.tmux/plugins/tpm/tpm'\n"
        )
        self.cfg.tmux_conf_path.write_text(content)

    def ensure_plugins(self) -> None:
        ensure_dirs([self.cfg.plugins_dir, self.cfg.resurrect_dir])
        clones = [
            (TPM_REPO, self.cfg.plugins_dir / "tpm"),
            (RESURRECT_REPO, self.cfg.plugins_dir / "tmux-resurrect"),
            (CONTINUUM_REPO, self.cfg.plugins_dir / "tmux-continuum"),
        ]
        for repo, dest in clones:
            if not dest.exists():
                run(["bash", "-lc", f"git clone {repo} {dest}"], check=False)

        run(["bash", "-lc", "tmux start-server || true"], check=False)
        tpm_install = self.cfg.plugins_dir / "tpm" / "bin" / "install_plugins"
        if tpm_install.exists():
            run(["bash", "-lc", str(tpm_install)], check=False)

    def start_server(self) -> bool:
        res = run(["tmux", "start-server"], check=False)
        return res.code == 0

    def is_server_running(self) -> bool:
        res = run(["bash", "-lc", "tmux info >/dev/null 2>&1"], check=False)
        if res.code == 0:
            return True
        # tmux info exits 1 when no server; treat other errors as not running
        return False

    def new_session(self, name: str, cmd: str | None = None) -> None:
        run(["tmux", "start-server"], check=False)
        ls = run(["tmux", "ls"], check=False)
        if any(line.split(":")[0] == name for line in ls.out.splitlines() if line.strip()):
            return
        if cmd:
            run(["tmux", "new-session", "-s", name, "-d", "bash", "-lc", cmd], check=False)
        else:
            run(["tmux", "new-session", "-s", name, "-d"], check=False)
        self.initial_save()

    def kill_session(self, name: str) -> None:
        run(["bash", "-lc", f"tmux kill-session -t {name} || true"], check=False)

    def list_sessions(self) -> list[str]:
        out = run(["tmux", "ls"], check=False)
        names: list[str] = []
        for line in out.out.splitlines():
            if not line.strip():
                continue
            names.append(line.split(":")[0])
        return names

    def initial_save(self) -> None:
        save = self.cfg.plugins_dir / "tmux-resurrect" / "scripts" / "save.sh"
        if save.exists():
            run([str(save)], check=False)
