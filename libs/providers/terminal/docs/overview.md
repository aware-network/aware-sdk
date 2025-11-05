---
title: "aware-terminal providers overview"
code_path: "aware_terminal_providers/__init__.py"
test_path: "tests/test_registry.py"
code_sha: "TODO"
test_sha: "TODO"
last_validated: null
---

# aware-terminal Providers

This document snapshots the initial provider registry scaffolding for `aware-terminal`.

## Summary

- `tools/terminal/aware_terminal/providers/base.py` hosts the canonical provider interface and action payload returned to the CLI.
- `tools/terminal/aware_terminal/providers/registry.py` exposes the shared registry that terminal commands consume.
- `aware_terminal_providers/core/` offers reusable helpers (installer scaffolding, environment utilities, adapter base class).
- Provider implementations live under `aware_terminal_providers/providers/<slug>/` (Codex, Claude Code, Gemini), each registering with the shared registry. All three now expose install/update detection (auto-install optional via `AWARE_TERMINAL_PROVIDERS_AUTO_INSTALL=1`) and return launch/resume specs.
- Release manifests (`providers/<slug>/releases.json`) track validated versions per channel; update them via `scripts/update_provider_versions.py` when network access is available.

## Next Steps

- Replace stub providers with concrete implementations that wrap install/update/resume/launch logic.
- Capture validation hashes in `code_sha` and `test_sha` after the first end-to-end test pass.
