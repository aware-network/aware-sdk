# Terminal Selection Decision (Default: Kitty)

## Summary
For Aware’s “auto-launch → tmux attach → GNOME auto-move” pipeline on Ubuntu 24.04, Kitty is the default terminal backend. WezTerm is supported, but Flatpak builds are sandboxed and unsuitable for launcher-driven tmux attach; prefer native installs for WezTerm if used.

## Options Considered
- Kitty (default)
  - Pros: GPU-accelerated; built-in tabs/splits/layouts; powerful remote control API (`kitty @`) for scripting windows/tabs/titles/layouts; native apt packages; works on X11/Wayland; seamless with tmux attach.
  - Cons: No built-in SSH domain orchestration like WezTerm.
- WezTerm
  - Pros: Feature-rich (tabs/splits, mux server, SSH domains); Lua config; great long-term fit.
  - Cons: Flatpak build is sandboxed (not suitable for `tmux attach` launchers); apt repo path for Ubuntu 24.04 may be unreliable; native install required for use as launcher backend.
- Alacritty
  - Pros: Fast, minimal, simple TOML config.
  - Cons: No native tabs/splits by design—relies entirely on tmux; fewer orchestration hooks.
- GNOME Terminal
  - Pros: Stable baseline, apt-installed, integrates well with GNOME.
  - Cons: Limited automation relative to Kitty/WezTerm.

## Decision
- Default backend: Kitty
- Rationale: Best automation surface today; frictionless install; robust with tmux; ideal for Aware’s OS-level, programmatic workspace restoration.
- WezTerm policy: Supported, but only via native (non-Flatpak) install for launcher use. Flatpak WezTerm can be installed for personal use, but launchers will fall back to another terminal.

## Implementation Notes
- CLI default `--terminal` is `kitty`. `--auto` guided setup offers Kitty first.
- Launchers: Exec lines use `kitty -e tmux attach -t <session>` (or equivalent for other terminals).
- GNOME Auto Move Windows is used for workspace placement and works on X11/Wayland.

## Future Enhancements
- Kitty remote control integration for declarative layouts (tabs/titles/arrangements) atop tmux sessions.
- Optional WezTerm Lua config generator and native installer detection.

