# Changelog

All notable changes to `aware-release-pipeline` will be documented here.

## [Unreleased]
- Added pipeline registry with `pipeline list` / `pipeline run` CLI commands and built-in flows (`cli-bundle`, `cli-rules`, `terminal-providers`, `cli-release-e2e`).
- `cli-release-e2e` now builds the aware-cli wheel automatically (uv build), accepts optional extra wheels, and emits build receipts alongside bundle/rules/tests/workflow/publish outputs.
- Surfaced shared secret diagnostics via the aware-release resolver metadata for workflow troubleshooting.

## [0.1.0] - 2025-10-24
- Initial scaffold with prepare/publish orchestrator and CLI entrypoint.
- Added smoke tests covering bundle + publish workflows with noop adapter.
