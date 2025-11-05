from __future__ import annotations

from aware_terminal.core.util import run, which
from aware_terminal.doctor.context import DoctorContext
from aware_terminal.doctor.models import (
    DoctorCheckResult,
    DoctorMessage,
    DoctorMessageLevel,
    DoctorStatus,
)
from aware_terminal.doctor.models import combine_status


def _detect_version(binary: str) -> str | None:
    result = run([binary, "--version"], check=False)
    output = result.out.strip()
    return output or None


def _has_flatpak_wezterm() -> bool:
    result = run(
        [
            "bash",
            "-lc",
            "flatpak list --app 2>/dev/null | grep -q org.wezfurlong.wezterm && echo yes || echo no",
        ],
        check=False,
    )
    return result.out.strip() == "yes"


def run_terminal_check(context: DoctorContext) -> DoctorCheckResult:
    kitty_path = which("kitty")
    wezterm_path = which("wezterm")
    alacritty_path = which("alacritty")
    gnome_terminal_path = which("gnome-terminal")
    flatpak_wezterm = _has_flatpak_wezterm()

    messages: list[DoctorMessage] = []
    status = DoctorStatus.OK

    if kitty_path:
        ver = _detect_version("kitty")
        version_note = f" ({ver})" if ver else ""
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.SUCCESS,
                text=f"kitty present at {kitty_path}{version_note}",
            )
        )
    else:
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.WARNING,
                text="kitty not found (will fall back to other terminals)",
            )
        )
        status = combine_status(status, DoctorStatus.WARNING)

    if wezterm_path:
        ver = _detect_version("wezterm")
        version_note = f" ({ver})" if ver else ""
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.SUCCESS,
                text=f"wezterm present at {wezterm_path}{version_note}",
            )
        )
    elif flatpak_wezterm:
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.WARNING,
                text="wezterm available via Flatpak (not used for tmux launchers)",
            )
        )
        status = combine_status(status, DoctorStatus.WARNING)
    else:
        messages.append(
            DoctorMessage(level=DoctorMessageLevel.INFO, text="wezterm not detected")
        )

    if not (kitty_path or wezterm_path or flatpak_wezterm):
        if alacritty_path or gnome_terminal_path:
            fallback = alacritty_path or gnome_terminal_path
            messages.append(
                DoctorMessage(
                    level=DoctorMessageLevel.WARNING,
                    text=f"No preferred terminals found; fallback detected at {fallback}.",
                )
            )
            status = combine_status(status, DoctorStatus.WARNING)
        else:
            messages.append(
                DoctorMessage(
                    level=DoctorMessageLevel.ERROR,
                    text="No compatible terminal binaries detected. Install kitty or wezterm.",
                )
            )
            status = combine_status(status, DoctorStatus.ERROR)

    summary = "Terminal backends detected"
    return DoctorCheckResult(
        slug="terminals",
        title="Terminal Backends",
        status=status,
        summary=summary,
        messages=messages,
        data={
            "kitty_path": kitty_path,
            "wezterm_path": wezterm_path,
            "flatpak_wezterm": flatpak_wezterm,
            "fallbacks": {
                "alacritty": alacritty_path,
                "gnome-terminal": gnome_terminal_path,
            },
        },
    )
