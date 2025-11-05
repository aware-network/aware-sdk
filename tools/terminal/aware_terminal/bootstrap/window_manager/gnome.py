from __future__ import annotations

from typing import List, Optional, Tuple

import json
from pathlib import Path

from aware_terminal.bootstrap.gnome import (
    ExtensionInstallResult,
    ExtensionStatus,
    GnomeAutoMoveManager,
)
from aware_terminal.core.config import ToolConfig
from aware_terminal.core.env import EnvironmentInspector
from aware_terminal.core.util import ensure_dirs
from .base import WindowPlacementManager, WindowPlacementResult
from .layouts import load_layout_manifest, apply_layouts


class GnomeWindowPlacementManager(WindowPlacementManager):
    def __init__(self, cfg: ToolConfig):
        self.cfg = cfg
        self.manager = GnomeAutoMoveManager(cfg)
        self._last_install: Optional[ExtensionInstallResult] = None
        self._requires_reload: bool = False

    def capabilities(self) -> dict:
        status = self.manager.extension_status()
        extension_caps = status.to_dict()
        if self._requires_reload:
            extension_caps["requires_reload"] = True
            extension_caps.setdefault("message", "Reload GNOME Shell to apply changes.")
            extension_caps.setdefault("reload_hint", self._reload_hint())
        if self._last_install and self._last_install.install_source:
            extension_caps.setdefault("install_source_detail", self._last_install.install_source)

        rules_caps = self._rules_capabilities()

        return {
            "extension": extension_caps,
            "cli": {"available": status.cli_available},
            "rules": rules_caps,
        }

    def ensure_ready(self, auto: bool) -> WindowPlacementResult:
        self._requires_reload = False
        status = self.manager.extension_status()
        rules_caps = self._rules_capabilities()
        data = {
            "extension": status.to_dict(),
            "rules": rules_caps,
        }
        if self._last_install and self._last_install.install_source:
            data["extension"]["install_source_detail"] = self._last_install.install_source

        if not auto:
            if not status.installed:
                return WindowPlacementResult(
                    status="manual",
                    summary="Install GNOME Auto Move Windows extension",
                    command=["uv", "run", "aware-terminal", "gnome", "fix"],
                    data=data,
                )
            if status.installed and rules_caps.get("count", 0) == 0:
                return WindowPlacementResult(
                    status="manual",
                    summary="Seed GNOME auto-move rules",
                    command=["uv", "run", "aware-terminal", "setup"],
                    data=data,
                )
            layout_result = self._apply_layouts()
            if layout_result:
                data["layouts"] = layout_result
            return WindowPlacementResult(status="success", summary="GNOME window placement ready", data=data)

        install_result: Optional[ExtensionInstallResult] = None
        if not status.installed:
            install_result = self.manager.install_extension(prefer_local=True)
            self._last_install = install_result
            data["install"] = install_result.to_dict()
            if not install_result.installed:
                data["extension"] = self.manager.extension_status().to_dict()
                return WindowPlacementResult(
                    status="manual",
                    summary="Install GNOME Auto Move Windows extension",
                    command=install_result.command or ["uv", "run", "aware-terminal", "gnome", "fix"],
                    message=install_result.message,
                    data=data,
                )
            status = self.manager.extension_status()
            data["extension"] = status.to_dict()
            if install_result.install_source:
                data["extension"]["install_source_detail"] = install_result.install_source

        # Ensure user extensions are allowed before enabling.
        self.manager.set_disable_user_extensions(False)

        extension_changed = False
        if not status.enabled:
            extension_changed = self.manager.enable_extension()
            status = self.manager.extension_status()
            data["extension"] = status.to_dict()
            if self._last_install and self._last_install.install_source:
                data["extension"]["install_source_detail"] = self._last_install.install_source
            if not status.enabled:
                return WindowPlacementResult(
                    status="manual",
                    summary="Enable GNOME Auto Move Windows extension",
                    command=["uv", "run", "aware-terminal", "gnome", "fix"],
                    message="Automatic enablement failed.",
                    data=data,
                )

        reload_needed = bool(
            (install_result and install_result.requires_reload) or extension_changed
        )
        if reload_needed:
            self._requires_reload = True
            data["extension"]["requires_reload"] = True
            data["extension"]["reload_hint"] = self._reload_hint()

        rules_caps = self._rules_capabilities()
        data["rules"] = rules_caps
        if rules_caps.get("count", 0) == 0:
            seeded, info = self._seed_rules()
            data["rules"].update(info)
            if not seeded:
                return WindowPlacementResult(
                    status="manual",
                    summary="Seed GNOME auto-move rules",
                    command=["uv", "run", "aware-terminal", "setup"],
                    message=info.get("message") or "No auto-move rules configured.",
                    data=data,
                )
            rules_caps = self._rules_capabilities()
            data["rules"] = {**rules_caps, **info}

        layout_result = self._apply_layouts()
        if layout_result:
            data["layouts"] = layout_result

        return WindowPlacementResult(status="success", summary="GNOME window placement ready", data=data)

    def describe(self) -> str:
        return "GNOME Auto Move Windows integration"

    # --------------------------------------------------------------------- helpers
    def _reload_hint(self) -> str:
        session_type = EnvironmentInspector().session_type()
        if session_type == "x11":
            return "Reload GNOME Shell (Alt+F2 → r)."
        return "Log out and back in to reload GNOME Shell."

    def _rules_capabilities(self) -> dict:
        manifest_present = self.cfg.window_rules_path.exists()
        try:
            rules = self.manager.get_rules()
        except Exception:
            rules = []
        preview = rules[:3]
        source = "manifest" if manifest_present else ("gsettings" if rules else "none")
        return {
            "count": len(rules),
            "preview": preview,
            "manifest_present": manifest_present,
            "source": source,
            "manifest_path": str(self.cfg.window_rules_path),
        }

    def _seed_rules(self) -> Tuple[bool, dict]:
        info: dict = {}
        manifest_path = self.cfg.window_rules_path
        rules: Optional[List[str]] = None

        manifest_info: dict = {}
        derived_info: dict = {}

        if manifest_path.exists():
            rules, manifest_info = self._load_rules_manifest(manifest_path)
            info.update(manifest_info)

        if not rules:
            rules, derived_info = self._derive_rules_from_desktops()
            info.update(derived_info)

        if not rules:
            info.setdefault("message", "No desktop launchers detected.")
            return False, info

        self.manager.set_rules(rules)
        info["applied"] = True
        info["count"] = len(rules)
        info.setdefault("source", manifest_info.get("source") or derived_info.get("source"))
        return True, info

    def _load_rules_manifest(self, path: Path) -> Tuple[Optional[List[str]], dict]:
        info: dict = {"source": "manifest", "path": str(path)}
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception as exc:
            info["message"] = f"Invalid manifest: {exc}"
            return None, info

        items = data.get("rules") if isinstance(data, dict) else None
        if not isinstance(items, list):
            info["message"] = "Manifest missing 'rules' list."
            return None, info

        entries: List[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            desktop = item.get("desktop")
            workspace = item.get("workspace")
            if isinstance(desktop, str) and isinstance(workspace, int):
                entries.append(f"{desktop}:{workspace}")

        if not entries:
            info["message"] = "Manifest contained no valid rules."
            return None, info

        info["count"] = len(entries)
        return entries, info

    def _derive_rules_from_desktops(self) -> Tuple[Optional[List[str]], dict]:
        info: dict = {"source": "derived"}
        desktop_files = sorted(self.cfg.applications_dir.glob("AwareTerm-*.desktop"))
        if not desktop_files:
            try:
                from aware_terminal.bootstrap.launcher import TerminalLauncherManager
            except Exception:
                TerminalLauncherManager = None  # type: ignore
            if TerminalLauncherManager is not None:
                try:
                    launcher = TerminalLauncherManager(self.cfg)
                    launcher.write_launcher("control", self.cfg.default_terminal, autostart=True)
                    candidate = self.cfg.applications_dir / launcher.desktop_id("control")
                    if candidate.exists():
                        desktop_files = [candidate]
                except Exception:
                    pass
        if not desktop_files:
            fallback = self.cfg.applications_dir / "AwareTerm-control.desktop"
            desktop_files = [fallback] if fallback.exists() else []

        if not desktop_files:
            info["message"] = "No AwareTerm desktop launchers found."
            return None, info

        rules: List[str] = []
        workspace = 1
        for desktop_file in desktop_files:
            rules.append(f"{desktop_file.name}:{workspace}")
            workspace = workspace + 1 if workspace < 10 else workspace

        info["count"] = len(rules)
        info["desktops"] = [d.name for d in desktop_files]

        ensure_dirs([self.cfg.window_rules_path.parent])
        payload = {
            "rules": [{"desktop": rule.split(":")[0], "workspace": int(rule.split(":")[1])} for rule in rules]
        }
        try:
            self.cfg.window_rules_path.write_text(json.dumps(payload, indent=2))
            info["manifest_written"] = True
        except Exception as exc:
            info["manifest_written"] = False
            info.setdefault("message", f"Failed to persist derived manifest: {exc}")

        return rules, info

    def _apply_layouts(self) -> dict:
        layouts = load_layout_manifest(self.cfg.window_layout_path)
        if not layouts:
            return {"status": "skipped", "message": "No layout manifest found."}
        try:
            return apply_layouts(self.cfg, layouts)
        except Exception as exc:
            return {"status": "failed", "message": str(exc)}
