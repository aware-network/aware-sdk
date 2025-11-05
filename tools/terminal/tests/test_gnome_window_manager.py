from __future__ import annotations

from pathlib import Path

from aware_terminal.bootstrap.gnome import ExtensionInstallResult, ExtensionStatus
from aware_terminal.bootstrap.window_manager.gnome import GnomeWindowPlacementManager
from aware_terminal.core.config import ToolConfig


class StubAutoMoveManager:
    def __init__(self) -> None:
        self.installed = False
        self.enabled = False
        self.rules: list[str] = ["AwareTerm-control.desktop:1"]
        self.install_calls: int = 0

    def extension_status(self) -> ExtensionStatus:
        return ExtensionStatus(
            installed=self.installed,
            enabled=self.enabled,
            cli_available=True,
            install_source="user",
        )

    def install_extension(self, *, prefer_local: bool = True, allow_system_packages: bool = False) -> ExtensionInstallResult:
        self.install_calls += 1
        self.installed = True
        return ExtensionInstallResult(
            installed=True,
            attempted=True,
            install_source="user-cli",
            requires_reload=True,
        )

    def set_disable_user_extensions(self, disabled: bool) -> None:
        pass

    def enable_extension(self) -> bool:
        if not self.enabled:
            self.enabled = True
            return True
        return False

    def get_rules(self) -> list[str]:
        return list(self.rules)

    def set_rules(self, rules: list[str]) -> None:
        self.rules = list(rules)


class StubAutoMoveFail(StubAutoMoveManager):
    def install_extension(self, *, prefer_local: bool = True, allow_system_packages: bool = False) -> ExtensionInstallResult:
        self.install_calls += 1
        return ExtensionInstallResult(
            installed=False,
            attempted=True,
            install_source=None,
            requires_reload=False,
            manual=True,
            message="zip missing",
            command=["uv", "run", "aware-terminal", "gnome", "fix"],
        )


def make_config(tmp_path: Path) -> ToolConfig:
    return ToolConfig(
        applications_dir=tmp_path / "apps",
        autostart_dir=tmp_path / "autostart",
        window_rules_path=tmp_path / "window_rules.json",
        window_layout_path=tmp_path / "layouts.json",
        tmux_conf_path=tmp_path / "tmux.conf",
        tmux_dir=tmp_path / "tmux",
        plugins_dir=tmp_path / "tmux" / "plugins",
        resurrect_dir=tmp_path / "tmux" / "resurrect",
        systemd_user_dir=tmp_path / ".config" / "systemd" / "user",
    )


def test_ensure_ready_marks_reload(tmp_path) -> None:
    cfg = make_config(tmp_path)
    cfg.applications_dir.mkdir(parents=True, exist_ok=True)

    manager = GnomeWindowPlacementManager(cfg)
    stub = StubAutoMoveManager()
    manager.manager = stub  # type: ignore[assignment]

    result = manager.ensure_ready(auto=True)
    assert result.status == "success"
    assert result.data is not None
    extension_data = result.data["extension"]
    assert extension_data.get("requires_reload") is True
    assert "reload_hint" in extension_data
    caps = manager.capabilities()
    assert caps["extension"].get("requires_reload") is True


def test_ensure_ready_manual_on_install_failure(tmp_path) -> None:
    cfg = make_config(tmp_path)
    manager = GnomeWindowPlacementManager(cfg)
    stub = StubAutoMoveFail()
    manager.manager = stub  # type: ignore[assignment]

    result = manager.ensure_ready(auto=True)
    assert result.status == "manual"
    assert result.command == ["uv", "run", "aware-terminal", "gnome", "fix"]
    assert result.data is not None
    assert result.data["install"]["manual"] is True


def test_seed_rules_uses_manifest(tmp_path) -> None:
    cfg = make_config(tmp_path)
    cfg.applications_dir.mkdir(parents=True, exist_ok=True)
    manifest = cfg.window_rules_path
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '{"rules": [{"desktop": "AwareTerm-control.desktop", "workspace": 2}]}\n',
        encoding="utf-8",
    )

    manager = GnomeWindowPlacementManager(cfg)
    stub = StubAutoMoveManager()
    stub.rules = []
    manager.manager = stub  # type: ignore[assignment]

    seeded, info = manager._seed_rules()
    assert seeded is True
    assert info["source"] == "manifest"
    assert stub.rules == ["AwareTerm-control.desktop:2"]


def test_apply_layouts_skipped_without_manifest(tmp_path) -> None:
    cfg = make_config(tmp_path)
    manager = GnomeWindowPlacementManager(cfg)
    stub = StubAutoMoveManager()
    manager.manager = stub  # type: ignore[assignment]

    result = manager._apply_layouts()
    assert result["status"] == "skipped"
