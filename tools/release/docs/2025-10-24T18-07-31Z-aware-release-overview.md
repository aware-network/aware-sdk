---
id: aware-release-overview
created: "2025-10-24T18:07:31Z"
updated: "2025-10-24T18:07:31Z"
author:
  agent: Codex
  process: fs-tooling
  thread: release-tooling
code_path: tools/release/aware_release/aware_release/__init__.py
test_path: tools/release/aware_release/tests/test_manifest_schema.py
code_sha: "TBD"
test_sha: "TBD"
last_validated: "TBD"
---

# aware-release Package Overview

The `aware_release` package centralises bundle assembly, manifest generation, and publishing helpers for aware-cli releases. It follows `docs/BEST_PRACTICES.md` with dedicated documentation and tests.

## Components
- `aware_release.bundle` — low-level helpers for staging bundles, manifests, lockfiles, and provider metadata.
- `aware_release.schemas` — Pydantic models that validate manifest and release index payloads consumed by Studio automation.
- `aware_release.cli` — command entrypoints used by `aware-cli release …` wrappers and future CI workflows.
- `aware_release.integrations` — helper modules for Studio activation and Kernel/ORM validation.

## Testing
- Placeholder tests live under `tools/release/aware_release/tests/`; update fixtures and assertions as functionality lands.

## Next Steps
- Implement bundle builder logic, manifest validation, and provider discovery.
- Flesh out CLI commands and align them with aware-cli wrappers.
- Wire package into CI once command surfaces stabilise.
