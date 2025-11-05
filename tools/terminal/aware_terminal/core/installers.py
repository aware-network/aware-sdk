from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import TerminalBackend
from .util import run, which


@dataclass
class InstallOutcome:
    attempted: bool
    succeeded: bool
    message: str = ""


class TerminalInstaller:
    """Install terminal backends in a predictable, explicit way.

    Policy:
      - WezTerm: prefer official APT repo on Ubuntu; Flatpak as fallback. Do not attempt Snap (no official Snap).
      - kitty/alacritty/gnome-terminal: install via apt.
    """

    def is_present(self, backend: TerminalBackend) -> bool:
        return which(backend.exec) is not None

    def has_wezterm_flatpak(self) -> bool:
        if not which("flatpak"):
            return False
        r = run(["bash", "-lc", "flatpak list --app 2>/dev/null | grep -q org.wezfurlong.wezterm && echo yes || echo no"], check=False)
        return r.out.strip() == "yes"

    def install(self, backend: TerminalBackend) -> InstallOutcome:
        name = backend.name
        if name == "wezterm":
            return self._install_wezterm()
        if name in ("kitty", "alacritty", "gnome-terminal"):
            return self._apt_install(name)
        return InstallOutcome(False, False, f"Unknown terminal backend: {name}")

    def _apt_install(self, package: str) -> InstallOutcome:
        run(["sudo", "apt", "update"], check=False)
        r = run(["sudo", "apt", "install", "-y", package], check=False)
        ok = r.code == 0
        return InstallOutcome(True, ok, r.err if not ok else "")

    def _install_wezterm(self) -> InstallOutcome:
        # Prefer Flatpak on Ubuntu 24.04 for reliability
        if not which("flatpak"):
            run(["sudo", "apt", "update"], check=False)
            run(["sudo", "apt", "install", "-y", "flatpak"], check=False)
        if which("flatpak"):
            run(["flatpak", "remote-add", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"], check=False)
            fp = run(["flatpak", "install", "-y", "flathub", "org.wezfurlong.wezterm"], check=False)
            if fp.code == 0:
                return InstallOutcome(True, True, "Installed via Flatpak")

        # Last resort: official installer script (may depend on apt repo availability)
        run(["sudo", "apt", "update"], check=False)
        run(["sudo", "apt", "install", "-y", "curl"], check=False)
        script = run(["bash", "-lc", "curl -fsSL https://wezfurlong.org/wezterm/install/ubuntu.sh | bash"], check=False)
        if script.code == 0 and which("wezterm"):
            return InstallOutcome(True, True, "Installed via official installer script")

        return InstallOutcome(True, False, "Failed to install WezTerm via Flatpak and script")

    def ensure_flatpak(self) -> bool:
        if which("flatpak"):
            return True
        run(["sudo", "apt", "update"], check=False)
        r = run(["sudo", "apt", "install", "-y", "flatpak"], check=False)
        return r.code == 0 and which("flatpak") is not None

    def cleanup_wezterm_repo(self) -> None:
        # Remove any previously added (broken) apt.fury.io repo entries
        run(["sudo", "rm", "-f", "/etc/apt/sources.list.d/wezterm.list"], check=False)
        run(["sudo", "rm", "-f", "/usr/share/keyrings/wezterm-archive-keyring.gpg"], check=False)
