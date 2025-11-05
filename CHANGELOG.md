# Changelog

## [0.7.0] - 2025-11-05
- Added `aware-environment` to the bundle so the environment contract ships alongside release/test/terminal tooling.
- Updated CLI smoke test expectations to surface environment and terminal versions.
- Refreshed documentation to position the SDK as the infrastructure foundation ahead of kernel/CLI milestones.

## [0.6.1] - 2025-11-05
- Bundled the OSS test manifests under `aware_sdk/configs/manifests/oss` and updated docs for the explicit manifest workflow.
- Raised the `aware-test-runner` floor to `0.2.0` (manifest-less installs now require explicit manifest selection).

## [0.6.0] - 2025-11-05
- Added `[terminal]` extra bundling `aware-terminal` and `aware-terminal-providers` for Studio integration workflows.
- Published the OSS test manifests under `aware_sdk/configs/manifests` for use with `aware-test-runner`.

## [0.5.1] - 2025-11-04
- Added `[test]` extra that bundles pytest tooling for monorepo suites.
- Documented optional test install and wired CI to consume the meta package.

## [0.5.0] - 2025-11-04T01:22:26Z
- Initial export including libs/file_system, tools/release, and tools/test-runner.

## [0.0.0] - 2025-10-31
- Initial scaffold for aware-sdk bundle.
