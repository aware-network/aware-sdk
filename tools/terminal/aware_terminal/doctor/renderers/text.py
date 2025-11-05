from __future__ import annotations

import click

from aware_terminal.doctor.models import (
    DoctorMessageLevel,
    DoctorReport,
    DoctorStatus,
    ProviderAction,
    ProviderActionStatus,
)

STATUS_ICON = {
    DoctorStatus.OK: ("✓", "green"),
    DoctorStatus.WARNING: ("⚠", "yellow"),
    DoctorStatus.ERROR: ("✗", "red"),
}

MESSAGE_ICON = {
    DoctorMessageLevel.SUCCESS: ("✓", "green"),
    DoctorMessageLevel.INFO: ("•", "cyan"),
    DoctorMessageLevel.WARNING: ("⚠", "yellow"),
    DoctorMessageLevel.ERROR: ("✗", "red"),
}

PROVIDER_ICON = {
    ProviderActionStatus.INSTALLED: ("✓", "green"),
    ProviderActionStatus.MISSING: ("⚠", "yellow"),
    ProviderActionStatus.UPDATE_AVAILABLE: ("⬆", "yellow"),
    ProviderActionStatus.PENDING: ("…", "cyan"),
}


def render_report(report: DoctorReport, audience: str = "human") -> None:
    if audience == "agent":
        _render_agent(report)
    else:
        _render_human(report, audience)


def _render_human(report: DoctorReport, audience: str) -> None:
    click.secho("AWARE Terminal Doctor", bold=True)
    click.secho(f"Audience: {audience.capitalize()}", fg="cyan")
    click.echo()

    _render_human_summary(report)
    click.echo()

    checks_by_slug = {check.slug: check for check in report.checks}
    rendered: set[str] = set()

    ordered_slugs = ["tmux", "gnome", "environment", "terminals", "providers"]
    for slug in ordered_slugs:
        if slug in rendered:
            continue
        check = checks_by_slug.get(slug)
        if check:
            if slug == "providers":
                _render_providers_section(report, check)
            else:
                _render_check_section(check)
            rendered.add(slug)

    for check in report.checks:
        if check.slug in rendered:
            continue
        _render_check_section(check)
        rendered.add(check.slug)

    _render_summary(report)


def _render_human_summary(report: DoctorReport) -> None:
    blocking = [check for check in report.checks if getattr(check, "blocking", False)]
    advisory = [
        check
        for check in report.checks
        if not getattr(check, "blocking", False) and check.status in (DoctorStatus.WARNING, DoctorStatus.ERROR)
    ]

    click.secho("Action Required", bold=True)
    if blocking:
        for check in blocking:
            click.secho(f"- {check.title}: {check.summary}", fg="red")
            if check.remediations:
                for remediation in check.remediations:
                    cmd = _format_command(remediation.command) if remediation.command else None
                    click.echo("    • " + remediation.summary)
                    if cmd:
                        click.echo("      command: " + cmd)
    else:
        click.echo("- None")

    click.echo()
    click.secho("Advisory", bold=True)
    if advisory:
        for check in advisory:
            click.secho(f"- {check.title}: {check.summary}", fg="yellow")
            if check.remediations:
                for remediation in check.remediations:
                    cmd = _format_command(remediation.command) if remediation.command else None
                    click.echo("    • " + remediation.summary)
                    if cmd:
                        click.echo("      command: " + cmd)
    else:
        click.echo("- None")


def _render_providers_section(report: DoctorReport, provider_check) -> None:
    click.secho("== Agent Providers ==", bold=True)
    if not report.provider_actions:
        click.echo("  (no providers registered)")
    else:
        for action in report.provider_actions:
            icon, color = PROVIDER_ICON.get(action.status, ("•", "cyan"))
            details = _describe_provider_action(action)
            click.secho(f"  {icon} {details}", fg=color)
    if provider_check:
        if provider_check.blocking:
            warning_msgs = [
                msg
                for msg in provider_check.messages
                if msg.level in (DoctorMessageLevel.WARNING, DoctorMessageLevel.ERROR)
            ]
            if warning_msgs:
                click.echo("  Blocking:")
                _render_messages(warning_msgs, indent=4)
            if provider_check.remediations:
                _render_remediations(provider_check.remediations, indent=4)
        else:
            updates = [act for act in report.provider_actions if act.status is ProviderActionStatus.UPDATE_AVAILABLE]
            if updates:
                click.echo("  (updates listed above; details available via --json)")
    click.echo()


def _render_check_section(check) -> None:
    click.secho(f"== {check.title} ==", bold=True)
    _render_messages(check.messages, indent=2)
    if check.remediations:
        _render_remediations(check.remediations, indent=4)
    click.echo()


def _render_summary(report: DoctorReport) -> None:
    click.secho("== Summary ==", bold=True)
    icon, color = STATUS_ICON.get(report.status, ("•", "cyan"))
    click.secho(f"{icon} Overall status: {report.status.value}", fg=color)
    if report.session_type:
        click.echo(f"Session type: {report.session_type}")
    blocking_rems = _collect_remediations(report, blocking_only=True)
    if blocking_rems:
        click.secho("Outstanding blocking actions:", fg="yellow")
        for remediation in blocking_rems:
            click.echo(f"- {remediation.summary}")
            if remediation.command:
                click.echo(f"  command: {_format_command(remediation.command)}")
            if remediation.docs_url:
                click.echo(f"  docs: {remediation.docs_url}")
    else:
        click.secho("No blocking actions remaining.", fg="green")


def _render_agent(report: DoctorReport) -> None:
    click.echo(f"status: {report.status.value}")
    click.echo(f"session_type: {report.session_type or 'unknown'}")
    click.echo("providers:")
    if not report.provider_actions:
        click.echo("  - slug: none")
    else:
        for action in report.provider_actions:
            click.echo("  - slug: " + action.slug)
            click.echo(f"    status: {action.status.value}")
            if action.cli_name:
                click.echo(f"    cli: {action.cli_name}")
            if action.package:
                click.echo(f"    package: {action.package}")
            if action.installed_version:
                click.echo(f"    installed_version: {action.installed_version}")
            if action.latest_version:
                click.echo(f"    latest_version: {action.latest_version}")
            if action.install_command:
                click.echo(f"    install_command: {_format_command(action.install_command)}")
            if action.docs_url:
                click.echo(f"    docs: {action.docs_url}")
    click.echo("checks:")
    for check in report.checks:
        click.echo(f"  - slug: {check.slug}")
        click.echo(f"    title: {check.title}")
        click.echo(f"    status: {check.status.value}")
        click.echo(f"    summary: {check.summary}")
    click.echo("remediations:")
    if report.remediations:
        for remediation in report.remediations:
            click.echo(f"  - summary: {remediation.summary}")
            if remediation.command:
                click.echo(f"    command: {_format_command(remediation.command)}")
            if remediation.docs_url:
                click.echo(f"    docs: {remediation.docs_url}")
    else:
        click.echo("  - none")


def _collect_remediations(report: DoctorReport, *, blocking_only: bool) -> list[DoctorRemediation]:
    rems: list[DoctorRemediation] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for check in report.checks:
        if blocking_only and not getattr(check, "blocking", False):
            continue
        for remediation in check.remediations:
            key = (remediation.summary, tuple(remediation.command or []))
            if key in seen:
                continue
            seen.add(key)
            rems.append(remediation)
    return rems


def _render_messages(messages, *, indent: int) -> None:
    for msg in messages:
        icon, color = MESSAGE_ICON.get(msg.level, ("•", "cyan"))
        click.secho(f"{' ' * indent}{icon} {msg.text}", fg=color)


def _render_remediations(remediations, *, indent: int) -> None:
    click.secho(f"{' ' * indent}Suggested actions:", fg="yellow")
    for remediation in remediations:
        click.echo(f"{' ' * indent}- {remediation.summary}")
        if remediation.command:
            click.echo(f"{' ' * (indent + 2)}command: {_format_command(remediation.command)}")
        if remediation.docs_url:
            click.echo(f"{' ' * (indent + 2)}docs: {remediation.docs_url}")


def _describe_provider_action(action: ProviderAction) -> str:
    cli_label = f" (CLI: {action.cli_name})" if action.cli_name else ""
    title = f"{action.title}{cli_label}"
    if action.status is ProviderActionStatus.INSTALLED:
        version_text = action.installed_version or "version unknown"
        return f"{title} — installed {version_text}"
    if action.status is ProviderActionStatus.UPDATE_AVAILABLE:
        installed = action.installed_version or "version unknown"
        latest = action.latest_version or "latest unknown"
        return f"{title} — installed {installed} (update {latest} available)"
    if action.status is ProviderActionStatus.MISSING:
        pkg = action.package or "package"
        return f"{title} — missing (install {pkg})"
    if action.status is ProviderActionStatus.PENDING:
        return f"{title} — automation pending"
    return f"{title} — status {action.status.value}"


def _format_command(cmd: list[str]) -> str:
    return " ".join(cmd)
