# Changelog

All notable changes to `aware-terminal` are documented here. Dates use UTC.

## [0.3.3] - 2025-11-05
- Made `ProviderManifestRefresher` resilient in packaged environments by falling back to the bundled CI update script when no refresh script is configured.
- Updated control-center CLI tests to synthesise runtime docs in temporary directories, decoupling test runs from repository `docs/runtime` assets.

## [0.3.2] - 2025-11-05
- Added README and LICENSE metadata to the published package and ensured the wheel includes CHANGELOG/README/LIC files for PyPI.

## [0.3.1] - 2025-11-04
- Added a `[test]` extra with pytest, pytest-asyncio, and pytest-mock so maintainers can run the terminal suites after installing the package.

## [0.3.0] - 2025-10-24
- Added `TmuxServiceOrchestrator` with systemd detection, tmux path resolution, and non-systemd fallback, enabling automated tmux setup via `aware-terminal`.
- Updated doctor tmux check to use the new orchestrator and report blocking/advisory states with structured capability data.
- Wired `aware-cli terminal setup --auto-confirm` to run the orchestrator and record structured tmux actions, avoiding duplicate manual steps.
- Extended bootstrap helpers (`TmuxManager`, `SystemdManager`) with new APIs (start_server, daemon reload/status, linger).
- Introduced window placement abstraction with GNOME backend and manifest-driven rule seeding (future-ready for other OSes).
- Added a remediation registry with state persistence so aware-cli setup/doctor share the same action plan, produce machine-readable results, and cache successful remediations under `~/.aware/terminal/setup_state.json`.
- Added deterministic provider manifest resolution via package introspection, automatic manifest freshness checks (with bundled fallback), and streaming setup output with themed icons.
- Hardened GNOME automation: bundled and hashed the Auto Move Windows extension, added non-sudo install paths, enriched doctor/setup capabilities, and improved `window rules` CLI workflows with validation and JSON export.

## [0.2.0] - 2025-10-13
- Added Control Center TUI (`aware-terminal control`) with selectable data providers.
- Introduced data provider protocol plus mock fixtures with tests.
- Implemented CLI-backed data provider that shells out to `aware-cli object` commands (with caching & state detection).
- Bundled fixture generator script to refresh mock data from current docs.
- Added `aware-terminal control-init` to create/refresh the `aware-control` tmux session, launcher, and workspace rule.
- Refactored `aware_terminal.control_center` package (provider/view-model/tui separation) and added binding management commands.

## [0.1.0] - 2025-09-25
- Initial release with tmux setup automation, session management CLI, and GNOME integration helpers.
