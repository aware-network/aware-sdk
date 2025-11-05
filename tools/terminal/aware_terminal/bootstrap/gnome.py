from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex
import shutil
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional
from zipfile import ZipFile

from ..core.config import ToolConfig
from ..core.util import ensure_dirs, run, which

AUTO_MOVE_UUID = "auto-move-windows@gnome-shell-extensions.gcampax.github.com"
ASSET_KEY = "auto_move_windows"


@dataclass
class ExtensionStatus:
    installed: bool
    enabled: bool
    cli_available: bool
    install_source: Optional[str] = None  # user | system | unknown
    requires_reload: bool = False
    message: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtensionInstallResult:
    installed: bool
    attempted: bool
    install_source: Optional[str] = None  # user-cli | user-local | system-package
    requires_reload: bool = False
    manual: bool = False
    message: Optional[str] = None
    command: Optional[List[str]] = None

    def to_dict(self) -> dict:
        return asdict(self)


class GnomeAutoMoveManager:
    def __init__(self, cfg: ToolConfig):
        self.cfg = cfg

    # --- Extension status / install helpers -------------------------------------------------
    def ensure_extension_installed(
        self, *, prefer_local: bool = True, allow_system_packages: bool = False
    ) -> bool:
        result = self.install_extension(prefer_local=prefer_local, allow_system_packages=allow_system_packages)
        return result.installed

    def install_extension(
        self, *, prefer_local: bool = True, allow_system_packages: bool = False
    ) -> ExtensionInstallResult:
        pre_status = self.extension_status()
        if pre_status.installed:
            return ExtensionInstallResult(
                installed=True,
                attempted=False,
                install_source=pre_status.install_source,
                requires_reload=False,
            )

        zip_path = self._assets_zip()
        if not zip_path.exists() or not self._verify_asset(zip_path):
            return ExtensionInstallResult(
                installed=False,
                attempted=False,
                manual=True,
                message="Extension bundle missing or invalid; install manually.",
                command=["uv", "run", "aware-terminal", "gnome", "fix"],
            )

        installed = False
        attempted = False
        requires_reload = False
        install_source_detail: Optional[str] = None

        def refresh_installed() -> bool:
            return self.is_extension_installed()

        if prefer_local:
            if self.has_cli():
                attempted = True
                if self._install_with_cli(zip_path):
                    installed = refresh_installed()
                    if installed:
                        install_source_detail = "user-cli"
                        requires_reload = True
            if not installed:
                attempted = True
                if self._install_from_assets(zip_path):
                    installed = refresh_installed()
                    if installed:
                        install_source_detail = "user-local"
                        requires_reload = True
        else:
            if self.has_cli():
                attempted = True
                if self._install_with_cli(zip_path):
                    installed = refresh_installed()
                    if installed:
                        install_source_detail = "user-cli"
                        requires_reload = True

        if not installed and allow_system_packages:
            attempted = True
            run(["bash", "-lc", "sudo apt update"], check=False)
            run(
                ["bash", "-lc", "sudo apt install -y gnome-shell-extensions gnome-shell-extension-prefs"],
                check=False,
            )
            installed = refresh_installed()
            if installed:
                install_source_detail = "system-package"
                requires_reload = True

        if not installed:
            return ExtensionInstallResult(
                installed=False,
                attempted=attempted,
                install_source=install_source_detail,
                manual=True,
                message="Automatic install failed; run aware-terminal gnome fix or install via package manager.",
                command=["uv", "run", "aware-terminal", "gnome", "fix"],
            )

        post_status = self.extension_status()
        return ExtensionInstallResult(
            installed=True,
            attempted=attempted,
            install_source=install_source_detail or post_status.install_source,
            requires_reload=requires_reload,
        )

    def extension_status(self) -> ExtensionStatus:
        cli_available = self.has_cli()
        installed = self.is_extension_installed()
        install_source = self._detect_install_source() if installed else None
        enabled = self.is_extension_enabled() if installed else False
        return ExtensionStatus(
            installed=installed,
            enabled=enabled,
            cli_available=cli_available,
            install_source=install_source,
        )

    def has_cli(self) -> bool:
        return which("gnome-extensions") is not None

    def extension_dir_present(self) -> bool:
        system = Path("/usr/share/gnome-shell/extensions") / AUTO_MOVE_UUID
        local = Path.home() / ".local/share/gnome-shell/extensions" / AUTO_MOVE_UUID
        return system.exists() or local.exists()

    def enable_extension(self) -> bool:
        was_enabled = self.is_extension_enabled()
        if was_enabled:
            return False
        if self.has_cli():
            run(["bash", "-lc", f"gnome-extensions enable {AUTO_MOVE_UUID} || true"], check=False)
        else:
            current = run(["bash", "-lc", "gsettings get org.gnome.shell enabled-extensions"], check=False).out.strip()
            if current.startswith("@as "):
                current = current[4:]
            try:
                arr = ast.literal_eval(current) if current else []
                if not isinstance(arr, list):
                    arr = []
            except Exception:
                try:
                    arr = json.loads(current.replace("'", '"')) if current else []
                except Exception:
                    arr = []
            if AUTO_MOVE_UUID not in arr:
                arr.append(AUTO_MOVE_UUID)
                run(["bash", "-lc", f"gsettings set org.gnome.shell enabled-extensions '{arr}'"], check=False)
        return not was_enabled and self.is_extension_enabled()

    def is_extension_installed(self) -> bool:
        if self.has_cli():
            r = run(["bash", "-lc", f"gnome-extensions info {AUTO_MOVE_UUID} >/dev/null 2>&1 && echo yes || echo no"])
            return r.out.strip() == "yes"
        return self.extension_dir_present()

    def is_extension_enabled(self) -> bool:
        r = run(["bash", "-lc", "gsettings get org.gnome.shell enabled-extensions"], check=False)
        return AUTO_MOVE_UUID in r.out.strip()

    def set_disable_user_extensions(self, disabled: bool) -> None:
        run(
            ["bash", "-lc", f"gsettings set org.gnome.shell disable-user-extensions {'true' if disabled else 'false'}"],
            check=False,
        )

    # --- Rule helpers -----------------------------------------------------------------------
    def add_rule(self, desktop_id: str, workspace: int) -> None:
        rules = [r for r in self.get_rules() if not r.startswith(f"{desktop_id}:")]
        rules.append(f"{desktop_id}:{workspace}")
        self.set_rules(rules)

    def remove_rule(self, desktop_id: str) -> None:
        rules = [r for r in self.get_rules() if not r.startswith(f"{desktop_id}:")]
        self.set_rules(rules)

    def get_rules(self) -> List[str]:
        text = self._get_app_list_raw()
        if text.startswith("@as"):
            text = re.sub(r"^@as ", "", text)
        try:
            return json.loads(text.replace("'", '"'))
        except Exception:
            return []

    def set_rules(self, rules: List[str]) -> None:
        joined = ", ".join("'" + r + "'" for r in rules)
        arr = f"[{joined}]"
        run(
            [
                "bash",
                "-lc",
                "gsettings set org.gnome.shell.extensions.auto-move-windows application-list " + arr,
            ],
            check=False,
        )

    def list_enabled_extensions_cli(self) -> List[str]:
        if not self.has_cli():
            return []
        res = run(["bash", "-lc", "gnome-extensions list --enabled || true"], check=False)
        return [line.strip() for line in res.out.splitlines() if line.strip()]

    # --- Internal helpers ------------------------------------------------------------------
    def _get_app_list_raw(self) -> str:
        res = run(
            [
                "bash",
                "-lc",
                "gsettings get org.gnome.shell.extensions.auto-move-windows application-list 2>/dev/null || echo '[]'",
            ]
        )
        return res.out.strip()

    def _assets_root(self) -> Path:
        env_override = os.environ.get("AWARE_TERMINAL_ASSETS_ROOT")
        if env_override:
            candidate = Path(env_override).expanduser()
            if candidate.exists():
                return candidate

        base = Path(__file__).resolve()
        ancestors = list(base.parents)
        for ancestor in ancestors:
            for candidate in (
                ancestor / "assets" / "gnome",
                ancestor / "terminal" / "assets" / "gnome",
                ancestor / "tools" / "terminal" / "assets" / "gnome",
                ancestor / "aware_terminal" / "assets" / "gnome",
            ):
                if candidate.exists():
                    return candidate

        raise FileNotFoundError("GNOME assets directory not found")

    def _assets_zip(self) -> Path:
        return self._assets_root() / "auto-move-windows.zip"

    def _manifest_path(self) -> Path:
        return self._assets_root() / "manifest.json"

    def _load_manifest(self) -> dict:
        manifest_path = self._manifest_path()
        if not manifest_path.exists():
            return {}
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _verify_asset(self, path: Path) -> bool:
        manifest = self._load_manifest()
        meta = manifest.get(ASSET_KEY) if isinstance(manifest, dict) else None
        if not isinstance(meta, dict):
            return False
        expected = meta.get("sha256")
        if not isinstance(expected, str):
            return False
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            return False
        return digest == expected

    def _install_with_cli(self, zip_path: Path) -> bool:
        quoted = shlex.quote(str(zip_path))
        result = run(["bash", "-lc", f"gnome-extensions install --force {quoted}"], check=False)
        return result.code == 0

    def _install_from_assets(self, zip_path: Path) -> bool:
        dest = Path.home() / ".local/share/gnome-shell/extensions" / AUTO_MOVE_UUID
        ensure_dirs([dest.parent])
        if dest.exists():
            try:
                shutil.rmtree(dest)
            except Exception:
                pass
        try:
            with ZipFile(zip_path) as zf:
                zf.extractall(dest.parent)
        except Exception:
            return False
        return dest.exists()

    def _detect_install_source(self) -> Optional[str]:
        system = Path("/usr/share/gnome-shell/extensions") / AUTO_MOVE_UUID
        local = Path.home() / ".local/share/gnome-shell/extensions" / AUTO_MOVE_UUID
        if local.exists():
            return "user"
        if system.exists():
            return "system"
        return None
