# aware-terminal-providers

`aware-terminal-providers` supplies provider automation primitives for `aware-terminal`. The package bridges to the terminal-owned provider interface/registry and registers concrete implementations so desktop agents can install, update, launch, and resume third-party coding assistants (OpenAI Codex, Anthropic Claude Code, Google Gemini, and future providers).

## Quickstart

```bash
# Run tests for the terminal provider registry
uv run --project libs/providers/terminal pytest

# Install the package locally (editable mode)
uv pip install -e libs/providers/terminal

# Trigger the GitHub workflow that refreshes provider manifests (agents/CI)
uv run --project tools/release-pipeline release-pipeline workflow trigger \
  --workflow update-providers \
  --dry-run
```
> When `aware_sdk` ships, the public story will use `aware-cli release terminal ...` commands; the release-pipeline invocation above is for maintainers and CI.

## Package Layout

```
aware_terminal_providers/
├── __init__.py          # Ensures aware-terminal is importable and re-exports the shared registry
├── core/                # Shared helpers (installer/env/runners, provider base class)
│   └── ...
└── providers/           # Provider implementations (one folder per provider)
    ├── codex/
    ├── claude_code/
    └── gemini/
scripts/
└── update_provider_versions.py  # Fetch npm dist-tags and refresh release manifests
```

The accompanying tests live under `tests/` and validate the registry contract.

## Current Status

- Registry scaffolding with stub providers for Codex, Claude Code, and Gemini (registry hosted in `tools/terminal/aware_terminal/providers/`).
- Codex, Claude Code, and Gemini adapters now surface install/update detection (opt-in auto install via `AWARE_TERMINAL_PROVIDERS_AUTO_INSTALL=1`) and return launch/resume specs ready for tmux orchestration. Version data is sourced from the checked-in `releases.json` manifests.
- Core helpers scaffolded for installer/env/runner abstractions ahead of full automation.
- CLI integration work is tracked in `docs/projects/aware-agent-foundation/tasks/terminal-providers/`.
- Real install/update/resume automation is pending provider SDK evaluations.
- Release automation is routed through the shared pipeline modules:
  - `release-pipeline workflow trigger --workflow update-providers` refreshes manifests via GitHub Actions.
  - Future `sdk build` orchestration will pull in the latest provider metadata alongside CLI bundles and rule versions.

## Updating Supported Versions

Run the manifest updater (requires network access):

```bash
UV_CACHE_DIR=/tmp/uv-cache \\
uv run --project libs/providers/terminal \\
  python scripts/update_provider_versions.py --write --verbose
```

This refreshes `providers/<slug>/releases.json`, which in turn powers the `SUPPORTED_VERSION` metadata used by aware-terminal doctor/setup.
- CLI integration work is tracked in `docs/projects/aware-agent-foundation/tasks/terminal-providers/`.
- Real install/update/resume automation is pending provider SDK evaluations.
