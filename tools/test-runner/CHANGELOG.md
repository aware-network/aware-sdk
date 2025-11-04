# Changelog

## [0.1.4] - 2025-11-04
- Relaxed workspace detection so aware-tests run against staged aware-sdk exports (falls back to pyproject markers or `AWARE_SDK_ROOT` when the monorepo isn't available).
- Added SDK sync tooling references to the release pipeline to keep public mirrors aligned.

## [0.1.3] - 2025-10-31T07:10:09Z
- Expanded OSS stable manifest to cover release-pipeline, test-runner, and file_system suites.
- Added changelog timestamp handling guard for manifests inserted without [Unreleased].

## [0.1.2] - 2025-10-31
- Polished README content, metadata classifiers/URLs, and MIT license for the public release.
- Exported `__version__` for downstream tooling and release pipelines.

## [0.1.1] - 2025-10-31T01:03:31Z
- Marked aware-tests stable suite green (skipped kernel ACL WIP, isolated secret resolver tests).
- Packaged OSS manifest defaults (grammar + CLI coverage) and hooked CI to use the manifest runner.
- Documented manifest directory env vars and bumped project version for first publish.

## [0.1.0] - 2025-10-26
- Scaffolded `aware-test-runner` package structure under `tools/`.
- Added initial README, optional dependency placeholders, and console script wiring for `aware-tests`.
- Reserved config and documentation directories for OSS/Internal manifest split.
- Migrated legacy runner modules into the package and added shims for `aware_tests` compatibility.
- Introduced manifest loader + CLI/env overrides (`--manifest`, `--manifest-file`) and refactored discovery to consume manifest data.
