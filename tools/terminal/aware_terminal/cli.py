from __future__ import annotations

import json
import click

from pathlib import Path

from typing import Optional

from .core.config import SessionConfig, ToolConfig, TerminalName, TerminalBackend
from .core.config_store import ConfigStore
from .core.env import EnvironmentInspector
from .resume.session import SessionOrchestrator
from .core.util import human_ago
from .integrations.bindings import BindingStore, Binding, ThreadBinding
from .providers import (
    ProviderActionResult,
    ProviderSessionResult,
    list_providers as terminal_list_providers,
    run_provider_action,
)
from .control_center import (
    ControlCenterViewModel,
    CliControlDataProvider,
    MockControlDataProvider,
    run_control_center,
    ControlAction,
)
import os
import time
from .core.util import run as run_cmd
from .bootstrap.control import ensure_control_session, SESSION_NAME
from .bootstrap.gnome import GnomeAutoMoveManager
from .bootstrap.window_manager.gnome import GnomeWindowPlacementManager
from .bootstrap.launcher import TerminalLauncherManager
from .daemon import ManifestStore, default_socket_path, manifest_path, TerminalDaemonClient
from .runtime.lifecycle import (
    start_daemon,
    stop_daemon,
    is_daemon_running,
    launch_daemon_subprocess,
    terminate_daemon_subprocess,
    LifecycleResult,
)
from .remediation import (
    build_context as build_remediation_context,
    execute_actions as execute_remediation_actions,
    RemediationPolicy,
    RemediationStatus,
)
from .remediation.manifest import ProviderManifestRefresher
from .remediation.rendering import NullRenderer, get_renderer
from .remediation.state import load_state as load_setup_state, save_state as save_setup_state
from .doctor import DoctorStatus, render_report as render_doctor_report, run_doctor


@click.group()
def cli() -> None:
    """AWARE Terminal Manager — persistent tmux + GNOME integration."""


def _emit_provider_result(provider: str, action: str, result):
    if result is None:
        raise click.ClickException(f"Provider '{provider}' is not registered.")

    if isinstance(result, ProviderSessionResult):
        click.echo(f"[{provider}] {action} -> session ready (id={result.session_id})")
        click.echo(f"  command: {' '.join(result.command)}")
        if result.cwd:
            click.echo(f"  cwd: {result.cwd}")
        if result.environment:
            click.echo("  env overrides:")
            for key, value in result.environment.items():
                click.echo(f"    {key}={value}")
        if result.extra_metadata:
            click.echo("  metadata:")
            for key, value in result.extra_metadata.items():
                click.echo(f"    {key}: {value}")
        return

    if not isinstance(result, ProviderActionResult):
        raise click.ClickException(f"Provider '{provider}' returned unexpected result type.")

    status = "success" if result.success else "pending"
    click.echo(f"[{provider}] {action} -> {status}: {result.message}")
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        for key, value in data.items():
            click.echo(f"  - {key}: {value}")
    if not result.success:
        raise SystemExit(1)


@cli.group()
def providers() -> None:
    """Manage aware-terminal provider automation."""


@providers.command("list")
def providers_list() -> None:
    entries = list(terminal_list_providers())
    if not entries:
        click.echo("No providers registered.")
        return
    for info in entries:
        click.echo(f"{info.slug}: {info.title}")
        click.echo(f"  {info.description}")


@providers.command("install")
@click.option("--provider", required=True, help="Provider slug (codex, claude-code, gemini, ...)")
def providers_install(provider: str) -> None:
    result = run_provider_action(provider, "install")
    _emit_provider_result(provider, "install", result)


@providers.command("update")
@click.option("--provider", required=True, help="Provider slug to update")
def providers_update(provider: str) -> None:
    result = run_provider_action(provider, "update")
    _emit_provider_result(provider, "update", result)


@providers.command("resume")
@click.option("--provider", required=True, help="Provider slug to resume")
@click.option("--session", help="Optional provider session identifier")
def providers_resume(provider: str, session: Optional[str]) -> None:
    result = run_provider_action(provider, "resume", session_id=session)
    _emit_provider_result(provider, "resume", result)


@providers.command("launch")
@click.option("--provider", required=True, help="Provider slug to launch")
@click.option("--resume", is_flag=True, help="Attempt to resume the last recorded session")
def providers_launch(provider: str, resume: bool) -> None:
    result = run_provider_action(provider, "launch", resume=resume)
    _emit_provider_result(provider, "launch", result)


@cli.command()
@click.option(
    "--terminal",
    type=click.Choice(["wezterm", "kitty", "alacritty", "gnome-terminal"]),
    default="kitty",
    help="Default terminal backend for launchers",
)
@click.option("--install-terminal", is_flag=True, help="Attempt to install the selected terminal")
@click.option(
    "--auto/--no-auto", default=True, help="Interactive guided setup (choose and install terminal, GNOME setup)"
)
@click.option("--with-wezterm", is_flag=True, help="Alias for --terminal=wezterm --install-terminal", hidden=True)
@click.option(
    "--provider-policy",
    type=click.Choice(["apply", "skip"]),
    default="apply",
    help="Provider automation policy when updating agents",
)
def setup(
    terminal: TerminalName,
    install_terminal: bool,
    auto: bool,
    with_wezterm: bool,
    provider_policy: str,
) -> None:
    """Install tmux + plugins, systemd user service, and GNOME integration."""
    from .core.util import which, run
    from .bootstrap.gnome import AUTO_MOVE_UUID

    # Back-compat alias
    if with_wezterm:
        terminal = "wezterm"
        install_terminal = True

    # Merge persisted default terminal preference
    store = ConfigStore()
    persisted = store.get_default_terminal()
    chosen_backend = TerminalBackend.from_name((terminal))
    if persisted:
        chosen_backend = persisted
        terminal = persisted.name  # reflect in logs
    cfg = ToolConfig(default_terminal=chosen_backend)
    orch = SessionOrchestrator(cfg)

    click.echo(f"→ Setup starting (terminal={terminal}, install_terminal={install_terminal}, auto={auto})")
    orch.setup(install_terminal=install_terminal)

    if auto:
        _guided_setup(cfg)

    # Post-checks (concise OK/FAIL lines)
    click.echo("→ Verifying environment...")
    # tmux.service
    en = run(["systemctl", "--user", "is-enabled", "tmux.service"], check=False).out.strip() == "enabled"
    ac = run(["systemctl", "--user", "is-active", "tmux.service"], check=False).out.strip() == "active"
    click.echo(f"tmux.service: enabled={en} active={ac}")

    # terminal
    term_path = which(cfg.default_terminal.exec)
    click.echo(f"terminal '{terminal}': present={bool(term_path)}{f' ({term_path})' if term_path else ''}")
    if term_path:
        ver = run([cfg.default_terminal.exec, "--version"], check=False)
        v = ver.out.strip() or ver.err.strip()
        if v:
            click.echo(f"{terminal} version: {v}")
    # extra: snap/flatpak presence and wezterm installation status
    if terminal == "wezterm":
        has_flatpak = bool(which("flatpak"))
        if not term_path:
            click.echo("WezTerm not detected. Recommended install (official script):")
            click.echo("  curl -fsSL https://wezfurlong.org/wezterm/install/ubuntu.sh | bash")
            if has_flatpak:
                click.echo("Alternative (Flatpak): flatpak install -y flathub org.wezfurlong.wezterm")

    # Prepare renderer for later stages
    renderer = get_renderer("human", interactive=auto, enable_color=os.environ.get("NO_COLOR") is None)

    # GNOME extension
    inst_cli = (
        run(
            ["bash", "-lc", f"gnome-extensions info {AUTO_MOVE_UUID} >/dev/null 2>&1 && echo yes || echo no"],
            check=False,
        ).out.strip()
        == "yes"
    )
    inst_fs = (
        run(
            [
                "bash",
                "-lc",
                f"test -d /usr/share/gnome-shell/extensions/{AUTO_MOVE_UUID} -o -d ~/.local/share/gnome-shell/extensions/{AUTO_MOVE_UUID} && echo yes || echo no",
            ],
            check=False,
        ).out.strip()
        == "yes"
    )
    enabled_list = run(["bash", "-lc", "gsettings get org.gnome.shell enabled-extensions"], check=False).out.strip()
    en_ext = AUTO_MOVE_UUID in enabled_list
    # Also show global 'disable-user-extensions'
    due = run(["bash", "-lc", "gsettings get org.gnome.shell disable-user-extensions"], check=False).out.strip()
    click.echo(
        f"Auto Move Windows: installed_cli={inst_cli} installed_fs={inst_fs} enabled={en_ext} disable_user_extensions={due}"
    )
    if not (inst_cli or inst_fs):
        click.echo("Hint: install with 'sudo apt install -y gnome-shell-extensions gnome-shell-extension-prefs'")
    elif not en_ext:
        click.echo(
            "Hint: enable with 'gnome-extensions enable auto-move-windows@gnome-shell-extensions.gcampax.github.com'"
        )
        click.echo("Then reload GNOME (X11: Alt+F2 → r) or log out/in (Wayland)")
    # Remediation registry summary
    if hasattr(renderer, "manifest_status"):
        renderer.manifest_status("Checking provider manifests…", level="info")
    refresher = ProviderManifestRefresher()
    refresh_result = refresher.ensure_fresh(allow_refresh=auto)
    if hasattr(renderer, "manifest_status"):
        level = {
            "fresh": "info",
            "refreshed": "info",
            "bundled": "info",
            "bundled-missing": "warning",
            "stale": "warning",
            "error": "error",
        }.get(refresh_result.status, "info")
        renderer.manifest_status(refresh_result.message, level=level)

    state = load_setup_state()
    if state is not None and refresh_result.timestamp is not None:
        state.manifests_refreshed_at = refresh_result.timestamp

    chosen_policy = RemediationPolicy(provider_policy)
    context = build_remediation_context(
        config=cfg,
        auto=auto,
        provider_policy=chosen_policy,
        state=state,
        interactive=getattr(renderer, "interactive", False),
    )
    outcomes = execute_remediation_actions(context, renderer=renderer)
    if auto:
        save_setup_state(state)

    def _format_command(value):
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return " ".join(str(part) for part in value)
        return str(value)

    click.echo("→ Remediation summary:")
    manual_outcomes = [o for o in outcomes if o.status in {RemediationStatus.MANUAL, RemediationStatus.FAILED}]
    summary_payload = {
        "executed": len(outcomes) - len(manual_outcomes),
        "manual": len(manual_outcomes),
        "manifest_status": refresh_result.status,
        "manifest_age_seconds": int(refresh_result.age.total_seconds()) if refresh_result.age else None,
        "manifest_message": refresh_result.message,
    }
    warnings_payload: list[str] = [o.summary for o in manual_outcomes]
    if refresh_result.status in {"stale", "error", "bundled-missing"}:
        warnings_payload.append(refresh_result.message)

    renderer.session_complete(summary_payload, warnings_payload)

    if isinstance(renderer, NullRenderer):
        if auto:
            for outcome in outcomes:
                if outcome.action_id.startswith("provider:"):
                    provider_name = outcome.summary.replace("Provider ", "")
                    status = "success" if outcome.status is RemediationStatus.EXECUTED else outcome.status.value
                    note = outcome.message or "handled"
                    click.echo(f"  Provider {provider_name}: {status} ({note})")
                    continue
                if outcome.status is RemediationStatus.EXECUTED:
                    click.echo(f"  ✓ {outcome.summary}")
                elif outcome.status is RemediationStatus.FAILED:
                    note = outcome.message or "failed"
                    click.echo(f"  ✗ {outcome.summary} ({note})")
                else:
                    cmd_text = _format_command(outcome.command) or (outcome.message or "manual follow-up required")
                    click.echo(f"  • {outcome.summary} → {cmd_text}")
        else:
            for outcome in outcomes:
                if outcome.status is RemediationStatus.EXECUTED:
                    continue
                cmd_text = _format_command(outcome.command) or (outcome.message or "")
                if outcome.action_id.startswith("provider:") and not cmd_text:
                    slug = outcome.action_id.split(":", 1)[1]
                    cmd_text = f"aware-cli terminal providers install {slug}"
                bullet = "-" if outcome.action_id.startswith("provider:") else "•"
                if cmd_text:
                    click.echo(f"  {bullet} {outcome.summary}: {cmd_text}")
                else:
                    click.echo(f"  {bullet} {outcome.summary}")
    click.echo("Setup complete ✅")


@cli.command()
@click.option(
    "--provider",
    type=click.Choice(["mock", "cli"]),
    default="cli",
    help="Data provider backend to use",
)
def control(provider: str) -> None:
    """Launch the Control Center TUI (Workspace 1)."""

    if provider == "mock":
        data_provider = MockControlDataProvider()
    elif provider == "cli":
        data_provider = CliControlDataProvider()
    else:
        raise click.ClickException(f"Unsupported provider: {provider}")

    try:
        view_model = ControlCenterViewModel(data_provider)
        action: ControlAction = run_control_center(view_model)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    if action.action == "attach":
        if not action.tmux_session:
            click.echo("No tmux session binding for this thread. Update bindings to enable auto attach.", err=True)
            return
        _attach_tmux_session(action.tmux_session)


@cli.command("control-init")
@click.option("--workspace", type=int, default=1, show_default=True, help="GNOME workspace index for dashboard window")
def control_init(workspace: int) -> None:
    """Ensure the aware-control tmux session, launcher, and workspace rule exist."""

    result = ensure_control_session()

    store = ConfigStore()
    backend = store.get_default_terminal()
    if backend is None:
        backend = TerminalBackend.from_name("kitty")
    cfg = ToolConfig(default_terminal=backend)
    launcher = TerminalLauncherManager(cfg)
    launcher.write_launcher(SESSION_NAME, backend, autostart=True)
    desktop_id = launcher.desktop_id(SESSION_NAME)

    # persist layout manifest so control center can be positioned consistently
    layout_path = cfg.window_layout_path
    layout_path.parent.mkdir(parents=True, exist_ok=True)
    wm_class = desktop_id.replace(".desktop", "")
    layout_payload = {
        "layouts": [
            {
                "desktop": desktop_id,
                "match": wm_class,
                "workspace": workspace,
            }
        ]
    }
    try:
        layout_path.write_text(json.dumps(layout_payload, indent=2))
    except OSError:
        pass

    gnome = GnomeAutoMoveManager(cfg)
    try:
        gnome.remove_rule(desktop_id)
    except Exception:
        pass
    gnome.add_rule(desktop_id, workspace)

    if result.created:
        click.echo(f"Created control session '{SESSION_NAME}'.")
    else:
        click.echo(f"Refreshed control session '{SESSION_NAME}'.")
    click.echo(f"Launcher updated (autostart on GNOME workspace {workspace}).")


@cli.group("control-bind")
def control_bind() -> None:
    """Manage control center thread bindings."""


@control_bind.command("set")
@click.option("--thread", required=True, help="Thread identifier (e.g. desktop/thread-123)")
@click.option("--session", required=True, help="tmux session name to attach")
@click.option("--workspace", type=int, help="GNOME workspace index (optional)")
def control_bind_set(thread: str, session: str, workspace: Optional[int]) -> None:
    store = BindingStore()
    store.set_thread(ThreadBinding(thread_id=thread, tmux_session=session, workspace=workspace))
    ws_text = f" workspace={workspace}" if workspace is not None else ""
    click.echo(f"Bound {thread} -> {session}{ws_text}")


@control_bind.command("list")
def control_bind_list() -> None:
    store = BindingStore()
    threads = store.list_threads()
    if not threads:
        click.echo("No thread bindings configured.")
        return
    for thread_id, data in threads.items():
        ws = data.get("workspace")
        ws_text = f" workspace={ws}" if ws is not None else ""
        click.echo(f"{thread_id}: session={data.get('session')}{ws_text}")


@control_bind.command("remove")
@click.option("--thread", required=True, help="Thread identifier to remove")
def control_bind_remove(thread: str) -> None:
    store = BindingStore()
    if store.remove_thread(thread):
        click.echo(f"Removed binding for {thread}.")
    else:
        click.echo(f"No binding found for {thread}.", err=True)


@cli.group()
def daemon() -> None:
    """Manage aware-terminal daemon manifests and status."""


@daemon.command("start")
@click.option("--thread", required=True, help="Thread identifier (t-...) to prepare")
@click.option("--socket", type=click.Path(), help="Optional Unix socket path override")
def daemon_start(thread: str, socket: Optional[str]) -> None:
    """Start the daemon in the background for the given thread."""

    socket_path = Path(socket).expanduser() if socket else None
    result = launch_daemon_subprocess(thread, socket_path=socket_path)
    if not result.ok:
        raise click.ClickException(result.message or result.error or "Failed to start daemon")

    click.echo(f"Daemon running for {thread} (socket: {result.socket_path})")
    click.echo(f"Manifest: {manifest_path(thread)}")


@daemon.command("status")
@click.option("--thread", required=True, help="Thread identifier (t-...) to inspect")
@click.option("--socket", type=click.Path(), help="Optional Unix socket path override")
def daemon_status(thread: str, socket: Optional[str]) -> None:
    """Display manifest details and list sessions (via daemon if available)."""

    manifest_file = manifest_path(thread)
    store = ManifestStore(manifest_file)
    try:
        manifest = store.load()
    except FileNotFoundError as exc:
        raise click.ClickException(
            f"Manifest not found for thread {thread}. Run 'aware-terminal daemon start --thread {thread}' first."
        ) from exc

    socket_path = Path(socket).expanduser() if socket else manifest.socket_path
    client = TerminalDaemonClient(socket_path=socket_path, manifest_store=store)
    try:
        sessions = client.list_sessions()
        source = "daemon" if socket_path.exists() else "manifest"
    except FileNotFoundError:
        sessions = manifest.sessions
        source = "manifest"

    click.echo(f"Thread: {manifest.thread}")
    click.echo(f"Daemon running: {is_daemon_running(thread)}")
    click.echo(f"Socket: {socket_path} (source={source})")
    if not sessions:
        click.echo("No sessions recorded.")
        return
    click.echo("Sessions:")
    for record in sessions:
        last_active = record.last_active_at.isoformat() if record.last_active_at else "--"
        click.echo(
            f"  - {record.session_id} (apt={record.apt_id}, window={record.tmux_window}, cwd={record.cwd}) last_active={last_active}"
        )


@daemon.command("stop")
@click.option("--thread", required=True, help="Thread identifier (t-...) to stop")
def daemon_stop(thread: str) -> None:
    """Stop the daemon launched via 'daemon start'."""

    result = terminate_daemon_subprocess(thread)
    if not result.ok:
        raise click.ClickException(result.message or result.error or "Daemon not running")
    click.echo(f"Stopped daemon for {thread}")


@daemon.command("serve")
@click.option("--thread", required=True, help="Thread identifier (t-...) to manage")
@click.option("--socket", type=click.Path(), help="Optional Unix socket path override")
@click.option(
    "--poll-interval",
    type=float,
    default=0.5,
    show_default=True,
    help="Polling interval (seconds) for tmux pane capture",
)
@click.option(
    "--once",
    is_flag=True,
    help="Start and stop immediately (testing/CI)",
)
def daemon_serve(thread: str, socket: Optional[str], poll_interval: float, once: bool) -> None:
    """Run the terminal daemon server (blocking)."""

    socket_path = Path(socket).expanduser() if socket else default_socket_path(thread)
    result = start_daemon(
        thread,
        socket_path=socket_path,
        detach=False,
        poll=True,
        poll_interval=poll_interval,
    )
    if not result.ok or result.server is None:
        raise click.ClickException(result.message or result.error or "Failed to start daemon")
    server = result.server
    click.echo(f"Daemon running for {thread} on {socket_path}.{' (once)' if once else ' Press Ctrl+C to stop.'}")
    try:
        if once:
            time.sleep(0.1)
        else:  # pragma: no branch - interactive loop
            while True:
                click.pause(info="")
    except (KeyboardInterrupt, click.Abort):  # pragma: no cover - interactive
        pass
    finally:
        click.echo("Stopping daemon...")
        server.stop()


def _attach_tmux_session(session_name: str) -> None:
    if os.environ.get("TMUX"):
        run_cmd(["tmux", "switch-client", "-t", session_name], check=False)
    else:
        run_cmd(["tmux", "attach", "-t", session_name], check=False)


def _guided_setup(cfg: ToolConfig) -> None:
    from .core.installers import TerminalInstaller
    from .bootstrap.gnome import AUTO_MOVE_UUID

    import click
    from .core.util import which, run

    installer = TerminalInstaller()
    current = cfg.default_terminal
    # Terminal preference order (Aware default: kitty)
    order: list[TerminalName] = ["kitty", "wezterm", "alacritty", "gnome-terminal"]
    if current.name in order:
        order.remove(current.name)
        order.insert(0, current.name)

    # Pick or install a terminal
    chosen = None
    click.echo("→ Guided terminal selection and installation")
    for name in order:
        backend = type(current).from_name(name)
        if installer.is_present(backend):
            click.echo(f"✓ Detected installed terminal: {name}")
            chosen = backend
            break
        if click.confirm(f"Install {name}?", default=(name == "kitty")):
            # Cleanup any broken WezTerm APT repo first
            if name == "wezterm":
                installer.cleanup_wezterm_repo()
            # Offer Flatpak bootstrap for WezTerm if missing
            if name == "wezterm" and not installer.ensure_flatpak():
                if click.confirm("Flatpak not found. Install Flatpak?", default=True):
                    installer.ensure_flatpak()
            click.echo(f"→ Installing {name} ...")
            outcome = installer.install(backend)
            click.echo(
                f"→ Install outcome: attempted={outcome.attempted} succeeded={outcome.succeeded} msg='{outcome.message}'"
            )
            if outcome.succeeded and installer.is_present(backend):
                click.echo(f"✓ Installed {name}")
                chosen = backend
                break
            # Special case: WezTerm via Flatpak present but no 'wezterm' binary
            if (
                name == "wezterm"
                and outcome.succeeded
                and installer.has_wezterm_flatpak()
                and not installer.is_present(backend)
            ):
                click.echo(
                    "✓ WezTerm Flatpak detected. Note: Flatpak cannot launch host tmux; using another terminal for launchers."
                )
                # do not choose wezterm; continue to next option
                continue
            else:
                click.echo(f"✗ Failed to install {name}: {outcome.message}")
                continue

    if chosen is None:
        click.echo("No terminal installed/detected. Launchers will not work until a terminal is available.")
    else:
        click.echo(f"Using terminal: {chosen.name}")
        # Persist preference for future runs
        ConfigStore().set_default_terminal(chosen.name)

    # GNOME extension
    click.echo("→ GNOME Auto Move Windows setup")
    inst_cli = (
        run(
            ["bash", "-lc", f"gnome-extensions info {AUTO_MOVE_UUID} >/dev/null 2>&1 && echo yes || echo no"],
            check=False,
        ).out.strip()
        == "yes"
    )
    inst_fs = (
        run(
            [
                "bash",
                "-lc",
                f"test -d /usr/share/gnome-shell/extensions/{AUTO_MOVE_UUID} -o -d ~/.local/share/gnome-shell/extensions/{AUTO_MOVE_UUID} && echo yes || echo no",
            ],
            check=False,
        ).out.strip()
        == "yes"
    )
    click.echo(f"→ Extension present: cli={inst_cli} fs={inst_fs}")
    if not (inst_cli or inst_fs):
        if click.confirm("Install GNOME Auto Move Windows extension packages?", default=True):
            run(["sudo", "apt", "update"], check=False)
            run(["sudo", "apt", "install", "-y", "gnome-shell-extensions", "gnome-shell-extension-prefs"], check=False)
            inst_cli = (
                run(
                    ["bash", "-lc", f"gnome-extensions info {AUTO_MOVE_UUID} >/dev/null 2>&1 && echo yes || echo no"],
                    check=False,
                ).out.strip()
                == "yes"
            )
            inst_fs = (
                run(
                    [
                        "bash",
                        "-lc",
                        f"test -d /usr/share/gnome-shell/extensions/{AUTO_MOVE_UUID} -o -d ~/.local/share/gnome-shell/extensions/{AUTO_MOVE_UUID} && echo yes || echo no",
                    ],
                    check=False,
                ).out.strip()
                == "yes"
            )
            click.echo(f"→ Extension present after install: cli={inst_cli} fs={inst_fs}")
    if inst_cli or inst_fs:
        en_list = run(["bash", "-lc", "gsettings get org.gnome.shell enabled-extensions"], check=False).out
        if AUTO_MOVE_UUID not in en_list and click.confirm("Enable Auto Move Windows extension?", default=True):
            # Try CLI, fallback to gsettings
            from .bootstrap.gnome import GnomeAutoMoveManager

            gm = GnomeAutoMoveManager(ToolConfig())
            # Ensure user extensions not globally disabled
            gm.set_disable_user_extensions(False)
            gm.enable_extension()
            # Prompt to reload and wait for confirmation on X11
            from .core.env import EnvironmentInspector

            session_type = EnvironmentInspector().session_type()
            if session_type == "x11":
                click.echo("Please reload GNOME Shell now: Alt+F2 → type 'r' → Enter")
                click.prompt("Press Enter after you have reloaded GNOME", default="", show_default=False)
                # Re-check enablement
                en_list2 = run(["bash", "-lc", "gsettings get org.gnome.shell enabled-extensions"], check=False).out
                cli_list = gm.list_enabled_extensions_cli()
                click.echo(f"→ Extension enabled after reload: {AUTO_MOVE_UUID in en_list2}")
                click.echo(f"→ CLI enabled list contains extension: {AUTO_MOVE_UUID in cli_list}")
            else:
                click.echo("On Wayland, log out and back in to finalize enablement.")


@cli.group()
def session() -> None:
    """Manage sessions (add/remove/list)."""


@session.command("add")
@click.option("--name", required=True, help="tmux session name")
@click.option("--workspace", required=True, type=int, help="GNOME workspace number (1-based)")
@click.option("--cmd", required=False, help="Command to run when creating the session")
@click.option("--init", multiple=True, help="Init command(s) to send when running --run-init or bindings")
@click.option("--autostart/--no-autostart", default=None, help="Create/update autostart entry for this session")
@click.option("--launch", is_flag=True, help="Launch a window for this session now")
def session_add(
    name: str, workspace: int, cmd: str | None, init: tuple[str, ...], autostart: bool | None, launch: bool
) -> None:
    cfg = ToolConfig()
    orch = SessionOrchestrator(cfg)
    if autostart is None:
        autostart_flag = orch.has_autostart(name)
    else:
        autostart_flag = autostart
    init_cmds = list(init) if init else None
    sess_cfg = SessionConfig(name=name, workspace=workspace, cmd=cmd, autostart=autostart_flag, init=init_cmds)
    orch.add_session(sess_cfg)
    click.echo(f"Session '{name}' added on workspace {workspace}.")
    # Respect user preference if flag not passed
    if not launch:
        from .core.config_store import ConfigStore

        launch = ConfigStore().get_launch_on_add()
    if launch:
        orch.launch_session_window(name)
        click.echo("Launched session window via desktop entry.")


@session.command("remove")
@click.option("--name", required=True, help="tmux session name")
@click.option("--kill", is_flag=True, help="Also kill the tmux session")
def session_remove(name: str, kill: bool) -> None:
    cfg = ToolConfig()
    orch = SessionOrchestrator(cfg)
    orch.remove_session(name=name, kill=kill)
    click.echo(f"Session '{name}' removed (kill={kill}).")


@session.command("list")
def session_list() -> None:
    cfg = ToolConfig()
    orch = SessionOrchestrator(cfg)
    for s in orch.list_sessions():
        click.echo(s)


@session.command("launch")
@click.option("--name", required=True, help="tmux session name")
def session_launch(name: str) -> None:
    cfg = ToolConfig()
    orch = SessionOrchestrator(cfg)
    orch.launch_session_window(name)
    click.echo(f"Launched session '{name}'.")


@cli.command("exec")
@click.option("--session", required=True, help="tmux session name")
@click.argument("cmd", nargs=-1)
def exec_cmd(session: str, cmd: tuple[str, ...]) -> None:
    """Send command to session's first pane and press Enter."""
    if not cmd:
        raise click.ClickException("Provide a command to send")
    cfg = ToolConfig()
    orch = SessionOrchestrator(cfg)
    orch.send_keys(session, " ".join(cmd))
    click.echo(f"Sent to {session}: {' '.join(cmd)}")


@cli.group()
def config() -> None:
    """User preferences (persisted in ~/.aware/terminal)."""


@config.command("show")
def config_show() -> None:
    store = ConfigStore()
    data = store.read()
    if not data:
        click.echo("(no config)")
        return
    # pretty print known keys first
    dt = data.get("default_terminal")
    loa = data.get("launch_on_add")
    if dt is not None:
        click.echo(f"default_terminal: {dt}")
    if loa is not None:
        click.echo(f"launch_on_add: {loa}")
    # dump any other keys
    for k, v in data.items():
        if k in ("default_terminal", "launch_on_add"):
            continue
        click.echo(f"{k}: {v}")


@config.command("set")
@click.option("--terminal", type=click.Choice(["wezterm", "kitty", "alacritty", "gnome-terminal"]))
@click.option("--launch-on-add/--no-launch-on-add", default=None, help="Launch windows by default after session add")
@click.option("--resume-default", type=click.Choice(["launch", "attach"]))
def config_set(terminal: TerminalName | None, launch_on_add: bool | None, resume_default: str | None) -> None:
    store = ConfigStore()
    if terminal:
        store.set_default_terminal(terminal)
        click.echo(f"default_terminal set to {terminal}")
    if launch_on_add is not None:
        store.set_launch_on_add(launch_on_add)
        click.echo(f"launch_on_add set to {launch_on_add}")
    if resume_default:
        store.set_resume_default(resume_default)
        click.echo(f"resume_default set to {resume_default}")
    else:
        click.echo("No change.")


@cli.group()
def gnome() -> None:
    """GNOME-specific actions (extensions, rules)."""


@gnome.command("fix")
def gnome_fix() -> None:
    """Ensure Auto Move Windows is installed, enabled, and GNOME is reloaded (guided)."""
    from .core.util import run
    from .bootstrap.gnome import AUTO_MOVE_UUID, GnomeAutoMoveManager

    click.echo("→ GNOME Auto Move Windows quick fix")
    gm = GnomeAutoMoveManager(ToolConfig())
    # Install packages if missing
    if not (gm.has_cli() or gm.extension_dir_present()):
        click.echo("→ Installing GNOME extension packages...")
        run(["sudo", "apt", "update"], check=False)
        run(["sudo", "apt", "install", "-y", "gnome-shell-extensions", "gnome-shell-extension-prefs"], check=False)
    # Enable
    click.echo("→ Enabling extension and allowing user extensions...")
    gm.set_disable_user_extensions(False)
    gm.enable_extension()
    # Prompt reload
    from .core.env import EnvironmentInspector

    if EnvironmentInspector().session_type() == "x11":
        click.echo("Please reload GNOME Shell now: Alt+F2 → type 'r' → Enter")
        click.prompt("Press Enter after you have reloaded GNOME", default="", show_default=False)
    else:
        click.echo("On Wayland, log out and back in to finalize.")
    # Verify
    en_list = run(["bash", "-lc", "gsettings get org.gnome.shell enabled-extensions"], check=False).out
    cli_list = gm.list_enabled_extensions_cli()
    click.echo(f"→ Enabled (gsettings): {AUTO_MOVE_UUID in en_list}")
    click.echo(f"→ Enabled (cli list): {AUTO_MOVE_UUID in cli_list}")


@cli.group()
def launcher() -> None:
    """Desktop launcher utilities."""


@launcher.command("migrate")
def launcher_migrate() -> None:
    """Rewrite AwareTerm-*.desktop Exec lines to use the wrapper script."""
    from .bootstrap.launcher import TerminalLauncherManager
    from .config import TerminalBackend
    from .core.config_store import ConfigStore
    import re

    store = ConfigStore()
    persisted = store.get_default_terminal()
    backend = persisted or TerminalBackend.from_name("kitty")
    cfg = ToolConfig(default_terminal=backend)
    lm = TerminalLauncherManager(cfg)

    updated = []
    for base in (cfg.applications_dir, cfg.autostart_dir):
        if not base.exists():
            continue
        for p in base.glob("AwareTerm-*.desktop"):
            session = p.stem[len("AwareTerm-") :]
            try:
                content = p.read_text()
            except Exception:
                continue
            new_exec = lm._exec_cmd(backend, session)
            if "Exec=" in content and new_exec not in content:
                content = re.sub(r"^Exec=.*$", f"Exec={new_exec}", content, flags=re.MULTILINE)
                if "Terminal=" not in content:
                    content = content.replace("StartupWMClass=", "Terminal=false\nStartupWMClass=")
                p.write_text(content)
                updated.append(str(p))

    if updated:
        click.echo("Updated launchers:\n" + "\n".join(updated))
    else:
        click.echo("No launchers updated.")


@cli.group()
def bind() -> None:
    """Manage provider → session bindings (codex, claude-code, etc.)."""


@bind.command("add")
@click.option("--provider", required=True, help="Provider key, e.g., 'codex'")
@click.option("--session", required=True, help="tmux session name")
@click.option("--init", required=False, help="Init command to run inside the session")
def bind_add(provider: str, session: str, init: str | None) -> None:
    store = BindingStore()
    store.set(Binding(provider=provider, session=session, init=init))
    click.echo(f"Bound {provider} → {session}{f' (init: {init})' if init else ''}")


@bind.command("list")
def bind_list() -> None:
    store = BindingStore()
    data = store.list()
    if not data:
        click.echo("(no bindings)")
        return
    for provider, info in data.items():
        click.echo(f"{provider}: session={info.get('session')} init={info.get('init')}")


@bind.command("remove")
@click.option("--provider", required=True)
def bind_remove(provider: str) -> None:
    store = BindingStore()
    if store.remove(provider):
        click.echo(f"Removed binding for {provider}")
    else:
        click.echo("Binding not found")


@bind.command("run")
@click.option("--provider", required=True)
@click.option("--launch", is_flag=True, help="Launch session window if needed")
def bind_run(provider: str, launch: bool) -> None:
    store = BindingStore()
    binding = store.get(provider)
    if not binding:
        raise click.ClickException(f"Binding not found for {provider}")
    cfg = ToolConfig()
    orch = SessionOrchestrator(cfg)
    if launch:
        orch.launch_session_window(binding.session)
    if binding.init:
        orch.send_keys(binding.session, binding.init)
    else:
        orch.attach_or_switch(binding.session)


@cli.group()
def profile() -> None:
    """Apply session profiles (YAML/JSON)."""


@profile.command("apply")
@click.option("--file", "file_path", type=click.Path(exists=True, dir_okay=False), help="Path to profile YAML/JSON")
@click.option("--name", help="Profile name under ~/.aware/terminal/profiles/<name>.yaml")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option("--launch-now", is_flag=True, help="Launch windows for each session after apply")
@click.option("--run-init", is_flag=True, help="Run per-session init commands after apply")
def profile_apply(file_path: str | None, name: str | None, dry_run: bool, launch_now: bool, run_init: bool) -> None:
    from .resume.profile import Profile
    from .config import TerminalBackend
    from .core.config_store import ConfigStore
    from .tmux import TmuxManager
    from .bootstrap.launcher import TerminalLauncherManager
    from .bootstrap.gnome import GnomeAutoMoveManager

    if not file_path and not name:
        raise click.ClickException("Provide --file or --name")
    if name and not file_path:
        base = ConfigStore().profiles_dir
        for ext in (".yaml", ".yml", ".json"):
            p = base / f"{name}{ext}"
            if p.exists():
                file_path = str(p)
                break
        if not file_path:
            raise click.ClickException(f"Profile '{name}' not found in {base}")
    assert file_path is not None
    prof = Profile.load(Path(file_path))

    # Merge terminal preference
    store = ConfigStore()
    if prof.terminal:
        store.set_default_terminal(prof.terminal)
    persisted = store.get_default_terminal()
    backend = persisted or TerminalBackend.from_name("kitty")
    cfg = ToolConfig(default_terminal=backend)
    if dry_run:
        # Inspect current state and print intended actions
        tm = TmuxManager(cfg)
        lm = TerminalLauncherManager(cfg)
        gm = GnomeAutoMoveManager(cfg)
        existing_sessions = set(tm.list_sessions())
        rules = gm.get_rules()
        click.secho("Dry Run — Profile Apply", bold=True)
        click.echo(f"Terminal backend: {backend.name}")
        for s in prof.sessions:
            click.echo(f"Session: {s.name}")
            if s.name in existing_sessions:
                click.echo("  • tmux: exists (no-op)")
            else:
                click.echo("  • tmux: create detached session")
            desktop_id = lm.desktop_id(s.name)
            app_path = cfg.applications_dir / desktop_id
            auto_path = cfg.autostart_dir / desktop_id
            click.echo(f"  • launcher: write {app_path}")
            if s.autostart:
                click.echo(f"  • autostart: ensure {auto_path}")
            else:
                click.echo(f"  • autostart: remove {auto_path}")
            rule = f"{desktop_id}:{s.workspace}"
            if any(r.startswith(f"{desktop_id}:") for r in rules):
                click.echo(f"  • gnome rule: replace → {rule}")
            else:
                click.echo(f"  • gnome rule: add → {rule}")
            if s.init:
                click.echo(f"  • init commands: {s.init}")
        click.secho("No changes applied (dry run)", fg="yellow")
        return
    # Apply
    cfg = ToolConfig(default_terminal=backend)
    orch = SessionOrchestrator(cfg)
    for s in prof.sessions:
        orch.add_session(s)
        click.echo(f"Applied session: {s.name} → workspace {s.workspace}")
        if launch_now:
            orch.launch_session_window(s.name)
        if run_init and s.init:
            for cmd in s.init:
                orch.send_keys(s.name, cmd)
            click.echo(f"  • ran init commands: {s.init}")
    if run_init:
        click.echo("Init commands executed for applicable sessions.")
    if launch_now:
        click.echo("Launched all sessions via desktop entries.")


@profile.command("new")
@click.option("--name", required=True, help="Profile name (saved under ~/.aware/terminal/profiles/<name>.yaml)")
@click.option(
    "--terminal",
    type=click.Choice(["wezterm", "kitty", "alacritty", "gnome-terminal"]),
    default="kitty",
    help="Terminal backend for this profile",
)
@click.option("--empty", is_flag=True, help="Create without example sessions")
@click.option("--force", is_flag=True, help="Overwrite if exists")
@click.option("--open", "open_editor", is_flag=True, help="Open in $EDITOR after create")
def profile_new(name: str, terminal: TerminalName, empty: bool, force: bool, open_editor: bool) -> None:
    from .resume.profile import Profile

    store = ConfigStore()
    path = store.profiles_dir / f"{name}.yaml"
    if path.exists() and not force:
        raise click.ClickException(f"Profile exists: {path} (use --force to overwrite)")
    prof = Profile.template(name=name, terminal=terminal, with_examples=not empty)
    prof.save_yaml(path)
    click.echo(f"Created profile: {path}")
    if open_editor:
        editor = os.environ.get("EDITOR")
        if not editor:
            click.echo("$EDITOR not set; please open the file manually.")
        else:
            import subprocess

            subprocess.run([editor, str(path)])


@profile.command("list")
def profile_list() -> None:
    store = ConfigStore()
    found = []
    for p in sorted(store.profiles_dir.glob("*")):
        if p.suffix.lower() in (".yaml", ".yml", ".json"):
            found.append(p.name)
    if not found:
        click.echo("(no profiles)")
    else:
        for name in found:
            click.echo(name)


@profile.command("show")
@click.option("--name", required=True)
def profile_show(name: str) -> None:
    from .resume.profile import Profile

    store = ConfigStore()
    path = None
    for ext in (".yaml", ".yml", ".json"):
        p = store.profiles_dir / f"{name}{ext}"
        if p.exists():
            path = p
            break
    if not path:
        raise click.ClickException(f"Profile not found: {name}")
    prof = Profile.load(path)
    click.echo(f"name: {prof.name}")
    click.echo(f"terminal: {prof.terminal}")
    click.echo("sessions:")
    for s in prof.sessions:
        click.echo(f"  - name: {s.name}\n    workspace: {s.workspace}\n    cmd: {s.cmd}")


@profile.command("remove")
@click.option("--name", required=True)
@click.option("--yes", is_flag=True, help="Do not prompt for confirmation")
def profile_remove(name: str, yes: bool) -> None:
    store = ConfigStore()
    path = None
    for ext in (".yaml", ".yml", ".json"):
        p = store.profiles_dir / f"{name}{ext}"
        if p.exists():
            path = p
            break
    if not path:
        raise click.ClickException(f"Profile not found: {name}")
    if not yes and not click.confirm(f"Delete profile {path}?", default=False):
        click.echo("Aborted")
        return
    path.unlink()
    click.echo(f"Deleted profile: {path}")


@cli.group()
def kitty() -> None:
    """Kitty terminal helpers (remote control, layouts)."""


@kitty.group("layout")
def kitty_layout() -> None:
    """Tab/window layout helpers."""


@kitty_layout.command("preview")
@click.option("--name", required=True, help="Profile name under ~/.aware/terminal/profiles")
def kitty_layout_preview(name: str) -> None:
    """Preview intended Kitty tab titles for the profile sessions."""
    from .kitty import KittyManager
    from .resume.profile import Profile

    store = ConfigStore()
    # Load profile
    path = None
    for ext in (".yaml", ".yml", ".json"):
        p = store.profiles_dir / f"{name}{ext}"
        if p.exists():
            path = p
            break
    if not path:
        raise click.ClickException(f"Profile not found: {name}")
    prof = Profile.load(path)
    km = KittyManager()
    click.secho("Kitty Layout Preview", bold=True)
    click.echo(f"Kitty installed: {km.is_installed()}")
    if km.is_installed():
        click.echo(f"Kitty version: {km.version()}")
    rc = km.rc_available()
    click.echo(f"Remote control available: {rc}")
    if not rc:
        click.echo("Tip: enable remote control (kitty.conf) or start kitty with '--listen-on unix:@mykitty'.")
    click.echo("Proposed tab titles (one per session):")
    for s in prof.sessions:
        click.echo(f"  - {s.name}")


@cli.command("resume")
@click.option("--name", help="Session name to resume")
@click.option("--launch", is_flag=True, help="Launch a window for the session (GNOME auto-move)")
@click.option("--pick", is_flag=True, help="Pick a session interactively if multiple")
def resume(name: str | None, launch: bool, pick: bool) -> None:
    """Resume a session. Without options, opens an interactive TUI picker."""
    cfg = ToolConfig()
    orch = SessionOrchestrator(cfg)
    # Interactive TUI when no explicit target/pick requested
    if not name and not pick and not launch:
        try:
            from .tui_resume import run_resume_tui
            from .core.util import log_append

            log_append("tui.log", "Starting TUI resume")
            result = run_resume_tui(cfg)
            log_append("tui.log", f"TUI result: {result}")
            action = result.get("action") or "none"
            target = result.get("name")
            if action == "attach" and target:
                orch.attach_or_switch(target)
                return
            if action == "launch" and target:
                orch.launch_session_window(target)
                return
            return
        except BaseException as e:
            from .core.util import log_append

            log_append("tui.log", f"TUI error: {type(e).__name__}: {e}")
            click.secho(f"TUI unavailable; falling back to list.", fg="yellow")

    items = orch.list_sessions_info()
    if not items:
        click.secho("No tmux sessions found.", fg="yellow")
        return
    # If name provided, resume it directly
    target_item = None
    if name:
        for it in items:
            if it["name"] == name:
                target_item = it
                break
        if not target_item:
            raise click.ClickException(f"Session not found: {name}")
    else:
        # Pretty list with recency
        import time

        now = int(time.time())
        click.secho("Resume Sessions", bold=True)
        ordered = sorted(items, key=lambda x: x["last_attached"], reverse=True)
        for idx, it in enumerate(ordered, start=1):
            ago = human_ago(max(0, now - (it["last_attached"] or it["created"])))
            ws = it.get("workspace")
            ws_s = f"ws {ws}" if ws else "ws ?"
            att = "attached" if it["attached"] else "detached"
            click.echo(f"{idx}. {it['name']}  ({ws_s}, {att}, {ago}, {it['windows']} windows)")
        if pick:
            choice = click.prompt("Select a session number", type=int)
            sel = choice - 1
            if sel < 0 or sel >= len(ordered):
                raise click.ClickException("Invalid selection")
            target_item = ordered[sel]
        else:
            if len(items) == 1:
                target_item = items[0]
            else:
                click.secho("Tip: use --pick to choose, --name <session>, or run without flags for TUI.", fg="cyan")
                return
    if launch:
        orch.launch_session_window(target_item["name"])  # type: ignore[index]
    else:
        orch.attach_or_switch(target_item["name"])  # type: ignore[index]


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable report (JSON).")
@click.option("--audience", type=click.Choice(["human", "agent"]), default="human", show_default=True)
def doctor(as_json: bool, audience: str) -> None:
    """Show environment and provider diagnostics with remediation guidance."""
    report = run_doctor()

    if as_json:
        payload = report.model_dump(mode="json")
        payload["audience"] = audience
        click.echo(json.dumps(payload, indent=2))
    else:
        render_doctor_report(report, audience=audience)

    if report.status is DoctorStatus.ERROR:
        raise click.ClickException("Doctor detected actionable errors.")


if __name__ == "__main__":
    cli()
@cli.group()
def window() -> None:
    """Window management helpers (rules, manifests)."""


@window.group()
def rules() -> None:
    """GNOME auto-move window rules management."""


@rules.command("export")
@click.option("--path", type=click.Path(), help="Output path for rules manifest.")
@click.option("--json", "as_json", is_flag=True, help="Write manifest to stdout instead of file.")
def window_rules_export(path: Optional[str], as_json: bool) -> None:
    cfg = ToolConfig()
    target = Path(path).expanduser() if path else cfg.window_rules_path
    manager = GnomeWindowPlacementManager(cfg)
    rules = manager.manager.get_rules()
    payload = {
        "rules": [
            {"desktop": entry.split(":")[0], "workspace": int(entry.split(":")[1])}
            for entry in rules
            if ":" in entry
        ]
    }
    if as_json:
        click.echo(json.dumps(payload, indent=2))
        if not path:
            return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    click.echo(f"Exported window rules to {target}")


@rules.command("apply")
@click.argument("path", type=click.Path(exists=True))
def window_rules_apply(path: str) -> None:
    cfg = ToolConfig()
    manager = GnomeWindowPlacementManager(cfg)
    manifest_path = Path(path).expanduser()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise click.ClickException(f"Failed to read manifest: {exc}") from exc

    items = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise click.ClickException("Manifest must contain a 'rules' array.")

    entries: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        desktop = item.get("desktop")
        workspace = item.get("workspace")
        if not isinstance(desktop, str) or not desktop.strip():
            raise click.ClickException("Each rule requires a non-empty 'desktop' field.")
        if not isinstance(workspace, int):
            raise click.ClickException("Each rule requires an integer 'workspace' field.")
        if workspace < 1 or workspace > 10:
            raise click.ClickException(f"Workspace must be between 1 and 10 (got {workspace}).")
        desktop_key = desktop.strip()
        if desktop_key in seen:
            raise click.ClickException(f"Duplicate desktop entry detected: {desktop_key}")
        seen.add(desktop_key)
        entries.append(f"{desktop_key}:{workspace}")

    if not entries:
        raise click.ClickException("No valid rules found in manifest.")

    manager.manager.set_rules(entries)
    manifest_payload = {
        "rules": [
            {"desktop": e.split(":")[0], "workspace": int(e.split(":")[1])}
            for e in entries
        ]
    }
    cfg.window_rules_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.window_rules_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
    if manifest_path != cfg.window_rules_path:
        manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
    click.echo(f"Applied {len(entries)} rules from {manifest_path}")
