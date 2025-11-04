---
id: release-pipeline-overview
created: "2025-10-25T00:03:56Z"
updated: "2025-10-25T00:03:56Z"
author:
  agent: Codex
  process: fs-tooling
  thread: release-tooling
code_path: tools/release-pipeline/aware_release_pipeline/cli.py
test_path: tools/release-pipeline/tests/test_pipeline.py
code_sha: TBD
test_sha: TBD
last_validated: TBD
---

# aware-release-pipeline Overview

`aware_release_pipeline` centralises bundle/publish orchestration required to ship aware-cli bundles to Studio. It wraps `aware_release` primitives while keeping secrets/config outside open-source tooling.

## Key Commands
- `release-pipeline prepare` – bundles wheels, validates manifest, and generates lockfiles.
- `release-pipeline publish` – pushes bundles using configured adapters (GitHub/S3/etc.), updating `releases.json`.

## Related Docs
- `docs/projects/aware-developer-tools/tasks/_pending/cli-release-bundles/design/2025-10-24T22-31-47Z-studio-cli-bundle-playbook.md`
- `aware_release` README for low-level adapters.
