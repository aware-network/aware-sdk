# Installation & Bundling Notes

This guide backs the `aware-release` bundle (aware-cli + aware-terminal + aware-terminal-providers + rules/release helpers). Install instructions live here so the main README can focus on the day-to-day experience.

## Prerequisites

- Ubuntu 24.04 (GNOME session)
- Python ≥ 3.12 (UV-managed virtualenv recommended)
- `tmux`, `git`, and build essentials will be installed automatically via setup/doctor when possible

## Install / Update

From the repo root:

```bash
source tools/aware-env.sh               # activate UV workspace defaults
uv run aware-terminal setup --auto      # guided setup (installs tmux plugins, systemd service, GNOME rules)
# or non-interactive via CLI:
uv run --project tools/cli aware-cli object call \
  --type terminal --function setup --id bootstrap \
  --auto-confirm --audience human
```

The setup flow:

1. Installs tmux + TPM plugins (`tmux-resurrect`, `tmux-continuum`)
2. Enables `tmux.service` (systemd user) so sessions auto-restore on login
3. Installs GNOME Auto Move Windows extension and seeds workspace rules
4. Installs terminal backends (kitty, wezterm, etc.) if requested
5. Probes `aware_terminal_providers` for Codex/Claude/Gemini adapters and runs their install hooks

Re-run `setup` anytime; it’s idempotent and caches remediations under `~/.aware/terminal/setup_state.json`.

## Provider Bundle

The provider package (`aware-terminal-providers`) exposes Codex, Claude, and Gemini adapters. It depends on `aware-terminal`, so the bundle must include both wheels.

Publish example:

```bash
uv build --project tools/terminal                      # builds aware-terminal wheel
uv build --project libs/providers/terminal             # builds aware-terminal-providers wheel
# upload or bundle into aware-release artefact
```

At runtime, `aware_terminal.providers` auto-imports `aware_terminal_providers`; adapters register themselves with the shared registry. If the providers package is missing, the registry stays empty but CLI/doctor commands surface “provider missing” diagnostics instead of crashing.

## Release Integration

The release pipeline (`tools/release-pipeline`) produces reproducible artefacts:

```bash
uv run --project tools/release-pipeline release-pipeline cli prepare \
  --channel stable --version 0.3.0 \
  --platform linux-x86_64 \
  --wheel dist/aware_cli-0.3.0-py3-none-any.whl

uv run --project tools/release-pipeline release-pipeline rules render \
  --version 0.3.0 \
  --rules-root docs/rules \
  --manifest build/rule-manifest.json
```

These commands will be wrapped by `aware-release` for public consumption; keep using them directly until the higher-level CLI ships.
