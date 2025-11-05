from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional, TextIO

try:
    import click
except Exception:  # pragma: no cover - click always available in runtime env, but guard for tests
    click = None  # type: ignore

from .themes import ActionTheme, DEFAULT_THEME, MINIMAL_THEME


class NullRenderer:
    """No-op renderer used for non-interactive or machine modes."""

    interactive: bool = False

    def manifest_status(self, *_args, **_kwargs) -> None:
        return

    def action_start(self, *_args, **_kwargs) -> None:
        return

    def provider_prompt(self, *_args, **_kwargs) -> None:
        return

    def confirm_provider(self, _prompt: str, default: bool = False) -> bool:
        return default

    def action_complete(self, *_args, **_kwargs) -> None:
        return

    def session_complete(self, *_args, **_kwargs) -> None:
        return


@dataclass
class RenderOptions:
    theme_name: str = "default"
    enable_color: bool = True
    stream: Optional[TextIO] = None
    interactive: bool = False


class RemediationRenderer:
    """Stream remediation events with optional color/icon support."""

    def __init__(self, options: RenderOptions) -> None:
        self._stream = options.stream or (click.get_text_stream("stdout") if click else sys.stdout)
        self._interactive = options.interactive
        self._enable_color = options.enable_color and hasattr(self._stream, "isatty") and self._stream.isatty()
        if options.theme_name == "minimal":
            self._theme = MINIMAL_THEME
        else:
            self._theme = DEFAULT_THEME

    @property
    def interactive(self) -> bool:
        return self._interactive

    def manifest_status(self, message: str, level: str = "info") -> None:
        icon = self._theme.actions.get("manifest", self._theme.default).icon
        color = self._color_for_level(level)
        self._emit(f"{icon} {message}", color=color, bold=False)

    def action_start(self, action_id: str, summary: str) -> None:
        theme = self._action_theme(action_id)
        self._emit(f"{theme.icon} {summary}…", color=self._theme.info_color)

    def provider_prompt(self, slug: str, title: str, details: Optional[dict]) -> None:
        theme = self._theme.actions.get("provider", self._theme.default)
        info = details or {}
        installed = info.get("installed_version")
        latest = info.get("latest_version")
        needs_update = info.get("needs_update")
        if needs_update is None:
            needs_update = bool(latest and installed and str(installed) != str(latest))

        if installed and latest:
            if str(installed) == str(latest):
                header = f"{theme.icon} {title} — installed {installed} (latest)"
                needs_update = False
            else:
                header = f"{theme.icon} {title} — {installed} → {latest}"
        elif installed:
            header = f"{theme.icon} {title} — installed {installed}"
        elif latest:
            header = f"{theme.icon} {title} — latest {latest}"
        else:
            header = f"{theme.icon} {title}"

        color = self._theme.warning_color if needs_update else self._theme.success_color
        self._emit(header, color=color, bold=True)

        if needs_update:
            summary = info.get("release_summary")
            if summary:
                self._emit(f"  notes: {summary}", color=self._theme.info_color)
            url = info.get("release_url")
            if url:
                self._emit(f"  docs: {url}", color=self._theme.info_color)

    def confirm_provider(self, prompt: str, default: bool = False) -> bool:
        if not self._interactive:
            return default
        if click is None:
            return default
        return click.confirm(prompt, default=default)

    def action_complete(self, action_id: str, status: str, message: Optional[str] = None) -> None:
        theme = self._action_theme(action_id)
        color = self._color_for_status(status)
        suffix = f" ({message})" if message else ""
        label = status.upper()
        self._emit(f"{theme.icon} {label}{suffix}", color=color, bold=status == "executed")

    def session_complete(self, summary: dict, warnings: list[str]) -> None:
        executed = summary.get("executed", 0)
        manual = summary.get("manual", 0)
        self._emit(f"[setup] completed actions: {executed}, manual follow-ups: {manual}", color=self._theme.success_color)
        for warning in warnings:
            self._emit(f"[warn] {warning}", color=self._theme.warning_color)

    # Internal helpers -------------------------------------------------
    def _emit(self, text: str, *, color: Optional[str] = None, bold: bool = False) -> None:
        if click and self._enable_color:
            click.secho(text, fg=color, bold=bold, file=self._stream)
        else:
            if bold:
                text = f"**{text}**"
            print(text, file=self._stream)

    def _action_theme(self, action_id: str) -> ActionTheme:
        if action_id.startswith("provider:"):
            return self._theme.actions.get("provider", self._theme.default)
        return self._theme.actions.get(action_id, self._theme.default)

    def _color_for_status(self, status: str) -> Optional[str]:
        mapping = {
            "executed": self._theme.success_color,
            "success": self._theme.success_color,
            "manual": self._theme.warning_color,
            "skipped": self._theme.warning_color,
            "failed": self._theme.error_color,
            "error": self._theme.error_color,
        }
        return mapping.get(status.lower())

    def _color_for_level(self, level: str) -> Optional[str]:
        mapping = {
            "info": self._theme.info_color,
            "warning": self._theme.warning_color,
            "error": self._theme.error_color,
        }
        return mapping.get(level.lower())


def get_renderer(audience: str, *, interactive: bool, enable_color: bool = True) -> RemediationRenderer | NullRenderer:
    stream = click.get_text_stream("stdout") if click else sys.stdout
    if audience != "human":
        return NullRenderer()
    options = RenderOptions(
        theme_name="default" if enable_color else "minimal",
        enable_color=enable_color,
        stream=stream,
        interactive=interactive,
    )
    return RemediationRenderer(options)
