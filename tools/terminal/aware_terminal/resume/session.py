from __future__ import annotations

from pathlib import Path

from ..core.config import SessionConfig, ToolConfig
from ..metadata import MetadataStore
from ..core.util import run
from ..bootstrap.tmux import TmuxManager
from ..bootstrap.systemd import SystemdManager
from ..bootstrap.tmux_service import TmuxServiceOrchestrator
from ..bootstrap.window_manager.gnome import GnomeWindowPlacementManager
from ..bootstrap.launcher import TerminalLauncherManager


class SessionOrchestrator:
    def __init__(self, cfg: ToolConfig):
        self.cfg = cfg
        self.tmux = TmuxManager(cfg)
        self.systemd = SystemdManager(cfg)
        self.tmux_service = TmuxServiceOrchestrator(cfg)
        self.gnome = GnomeWindowPlacementManager(cfg)
        self.launcher = TerminalLauncherManager(cfg)

    def setup(self, install_terminal: bool = False) -> None:
        self.tmux.ensure_installed()
        self.tmux.write_conf()
        self.tmux.ensure_plugins()
        self.tmux_service.ensure_service_ready(auto=True)
        self.gnome.ensure_ready(auto=True)

        if install_terminal:
            from ..core.installers import TerminalInstaller

            installer = TerminalInstaller()
            _ = installer.install(self.cfg.default_terminal)

    def add_session(self, sess: SessionConfig) -> None:
        self.tmux.new_session(sess.name, sess.cmd)
        self.launcher.write_launcher(sess.name, self.cfg.default_terminal, autostart=sess.autostart)
        desktop_id = self.launcher.desktop_id(sess.name)
        try:
            self.gnome.remove_rule(desktop_id)
        except Exception:
            pass
        self.gnome.add_rule(desktop_id, sess.workspace)

    def remove_session(self, name: str, kill: bool = False) -> None:
        desktop_id = self.launcher.desktop_id(name)
        for base in (self.cfg.applications_dir, self.cfg.autostart_dir):
            p = base / desktop_id
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        self.gnome.remove_rule(desktop_id)
        if kill:
            self.tmux.kill_session(name)

    def list_sessions(self) -> list[str]:
        return self.tmux.list_sessions()

    def launch_session_window(self, name: str) -> None:
        from ..core.util import spawn, which, log_append

        desktop_id = self.launcher.desktop_id(name)
        try:
            log_append("launch_debug.log", f"Launching session window: {name} (desktop_id={desktop_id})")
            desktop_file = self.cfg.applications_dir / desktop_id
            if desktop_file.exists() and which("gtk-launch"):
                log_append("launch_debug.log", f"Using gtk-launch with {desktop_id}")
                spawn(["gtk-launch", desktop_id])
            else:
                exec_cmd = self.launcher._exec_cmd(self.cfg.default_terminal, name)
                log_append("launch_debug.log", f"Fallback exec: {exec_cmd}")
                spawn(["bash", "-lc", exec_cmd])
        except Exception as exc:
            log_append("launch_debug.log", f"Error launching: {type(exc).__name__}: {exc}")

    def attach_or_switch(self, name: str) -> None:
        in_tmux = bool(run(["bash", "-lc", 'test -n "$TMUX" && echo yes || echo no'], check=False).out.strip() == "yes")
        if in_tmux:
            run(["tmux", "switch-client", "-t", name], check=False)
        else:
            run(["tmux", "attach", "-t", name], check=False)

    def send_keys(self, name: str, cmd: str) -> None:
        run(["tmux", "send-keys", "-t", f"{name}:0.0", cmd, "C-m"], check=False)

    def set_autostart(self, name: str, enable: bool) -> None:
        if enable:
            self.launcher.enable_autostart(name, self.cfg.default_terminal)
        else:
            self.launcher.disable_autostart(name)

    def has_autostart(self, name: str) -> bool:
        return self.launcher.autostart_path(name).exists()

    def list_sessions_info(self) -> list[dict]:
        fmt = "#{session_name}::#{session_windows}::#{?session_attached,1,0}::#{session_last_attached}::#{session_created}"
        res = run(["tmux", "list-sessions", "-F", fmt], check=False)
        info: list[dict] = []
        if res.code != 0:
            return info
        autostart_sessions = {
            path.stem[len("AwareTerm-") :]
            for path in self.cfg.autostart_dir.glob("AwareTerm-*.desktop")
        }
        metas = MetadataStore()
        for line in res.out.splitlines():
            parts = line.strip().split("::")
            if len(parts) != 5:
                continue
            name, windows, attached, last_attached, created = parts
            try:
                windows_i = int(windows)
                attached_b = attached == "1"
                last_i = int(last_attached) if last_attached else 0
                created_i = int(created) if created else 0
            except Exception:
                continue
            info.append(
                {
                    "name": name,
                    "windows": windows_i,
                    "attached": attached_b,
                    "last_attached": last_i,
                    "created": created_i,
                    "autostart": name in autostart_sessions,
                }
            )
        return info
