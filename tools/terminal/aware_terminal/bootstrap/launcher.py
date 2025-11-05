from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from ..core.config import TerminalBackend, ToolConfig

DESKTOP_ID_PREFIX = "AwareTerm-"


@dataclass
class LauncherSpec:
    """Declarative description of a desktop launcher."""

    slug: str
    command: str
    name: str
    startup_wm_class: Optional[str] = None
    autostart: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def desktop_id(self) -> str:
        suffix = ".desktop" if not self.slug.endswith(".desktop") else ""
        return f"{self.slug}{suffix}"


class TerminalLauncherManager:
    def __init__(self, cfg: ToolConfig):
        self.cfg = cfg

    def desktop_id(self, session: str) -> str:
        return f"{DESKTOP_ID_PREFIX}{session}.desktop"

    def launcher_path(self, session: str) -> Path:
        return self.cfg.applications_dir / self.desktop_id(session)

    def autostart_path(self, session: str) -> Path:
        return self.cfg.autostart_dir / self.desktop_id(session)

    def _ensure_wrapper(self) -> Path:
        bin_dir = Path.home() / ".aware" / "terminal" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        path = bin_dir / "aware-launch-session"
        if not path.exists():
            script = (
                "#!/usr/bin/env bash\n"
                "unset TMUX\n"
                "sess=\"$1\"\n"
                "logdir=\"$HOME/.aware/terminal/logs\"\n"
                "mkdir -p \"$logdir\"\n"
                "log=\"$logdir/launch.log\"\n"
                "{ date; echo \"Launching session: $sess\"; echo PATH=$PATH; which tmux || true; tty || true; } >> \"$log\" 2>&1\n"
                "if [ -z \"$sess\" ]; then echo 'Missing session name' >> \"$log\"; exec bash; fi\n"
                "TMUX_BIN=\"/usr/bin/tmux\"\n"
                "if [ ! -x \"$TMUX_BIN\" ]; then echo 'tmux not found' >> \"$log\"; exec bash; fi\n"
                "$TMUX_BIN has-session -t \"$sess\" >> \"$log\" 2>&1 || $TMUX_BIN new-session -ds \"$sess\" >> \"$log\" 2>&1\n"
                "$TMUX_BIN attach -t \"$sess\" >> \"$log\" 2>&1 || $TMUX_BIN new-session -As \"$sess\" >> \"$log\" 2>&1\n"
                "exec bash\n"
            )
            path.write_text(script)
            try:
                import os
                os.chmod(path, 0o755)
            except Exception:
                pass
        return path

    def _exec_cmd(self, backend: TerminalBackend, session: str) -> str:
        wrapper = str(self._ensure_wrapper())
        if backend.name == "wezterm":
            return f"{backend.exec} start -- {wrapper} {session}"
        if backend.name == "kitty":
            return f"{backend.exec} --title \"{session}\" -e {wrapper} {session}"
        if backend.name == "alacritty":
            return f"{backend.exec} -t \"{session}\" -e {wrapper} {session}"
        if backend.name == "gnome-terminal":
            return f"{backend.exec} --title=\"{session}\" -- {wrapper} {session}"
        return f"{backend.exec} {wrapper} {session}"

    def _render_entry(
        self,
        *,
        name: str,
        exec_cmd: str,
        startup_wm_class: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        lines = [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={name}",
            f"Exec={exec_cmd}",
            f"StartupWMClass={startup_wm_class or name.replace(' ', '-')}",
            "Terminal=false",
            "X-GNOME-Autostart-enabled=true",
        ]
        if metadata:
            for key, value in metadata.items():
                lines.append(f"X-Aware-{key}={value}")
        return "\n".join(lines) + "\n"

    def _render_session_entry(self, session: str, backend: TerminalBackend) -> str:
        startup_wm_class = DESKTOP_ID_PREFIX + session
        exec_cmd = self._exec_cmd(backend, session)
        name = f"{backend.name.title()} - {session}"
        return (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={name}\n"
            f"Exec={exec_cmd}\n"
            f"StartupWMClass={startup_wm_class}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )

    def write_launcher(self, session: str, backend: TerminalBackend, autostart: bool = False) -> Path:
        content = self._render_session_entry(session, backend)
        launcher_path = self.launcher_path(session)
        self.cfg.applications_dir.mkdir(parents=True, exist_ok=True)
        launcher_path.write_text(content)
        if autostart:
            self.enable_autostart(session, backend, content)
        else:
            self.disable_autostart(session)
        return launcher_path

    def write_spec(self, spec: LauncherSpec) -> Path:
        """Create or update a launcher based on the supplied spec."""

        self.cfg.applications_dir.mkdir(parents=True, exist_ok=True)
        content = self._render_entry(
            name=spec.name,
            exec_cmd=spec.command,
            startup_wm_class=spec.startup_wm_class,
            metadata=spec.metadata,
        )

        launcher_path = self.cfg.applications_dir / spec.desktop_id
        launcher_path.write_text(content)

        if spec.autostart:
            self.cfg.autostart_dir.mkdir(parents=True, exist_ok=True)
            (self.cfg.autostart_dir / spec.desktop_id).write_text(content)
        else:
            (self.cfg.autostart_dir / spec.desktop_id).unlink(missing_ok=True)

        return launcher_path

    def enable_autostart(self, session: str, backend: TerminalBackend, content: str | None = None) -> None:
        if content is None:
            content = self._render_session_entry(session, backend)
        self.cfg.autostart_dir.mkdir(parents=True, exist_ok=True)
        self.autostart_path(session).write_text(content)

    def disable_autostart(self, session: str) -> None:
        self.autostart_path(session).unlink(missing_ok=True)
