# Changelog

All notable changes to `aware-release` will be documented here.

## [0.1.2] - 2025-10-29T17:10:16Z
- Added resolver metadata to the shared secret registry (source, path, parse warnings) and exposed resolve_secret_info() for diagnostics.
- Improved workflow error reporting to enumerate attempted resolvers and guide maintainers to aware-cli release secrets-list.
- PyPI publish prep

## [0.1.1] - 2025-10-25
- Added MIT license, OSS-friendly metadata (classifiers/urls), and extended README for installation + usage guidance ahead of PyPI publication.
- Included README/LICENSE in wheel packaging and updated dependency alignment for release bundle tooling.
- Introduced release-pipeline helper and workflow to build/test and publish aware-release to PyPI.

## [0.1.0] - 2025-10-24
- Implemented functional bundle builder (wheel extraction, launch scripts, manifest embedding).
- Added provider packaging hooks, release object schemas, and CLI commands (bundle, manifest, locks, publish).
- Expanded tests covering bundle assembly, provider discovery, manifest validation, lock generation, and publish adapters.
