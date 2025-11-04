# aware-release-pipeline

Internal helper package that orchestrates `aware_release` commands for publishing aware-cli bundles. The goal is to keep CI workflows minimal while handling bundle→validate→publish logic in one place.

## Features
- Wraps `aware_release` primitives (bundle, manifest validation, lock generation, publish).
- Provides a single CLI entrypoint (`release-pipeline`) for release jobs.
- Logs structured JSON for each phase so Studio/CI can track results.

## Getting Started
```bash
uv sync --project tools/release-pipeline
uv run --project tools/release-pipeline pytest
```

## CLI Usage
```bash
# Prepare bundle + manifest + lock
uv run --project tools/release-pipeline release-pipeline cli prepare \
  --channel dev --version 0.1.0 \
  --platform linux-x86_64 \
  --wheel dist/aware_cli-0.1.0-py3-none-any.whl \
  --wheel dist/aware_terminal-0.2.0-py3-none-any.whl \
  --providers-dir providers/

# Publish using GitHub adapter (requires GH_TOKEN_RELEASE set)
uv run --project tools/release-pipeline release-pipeline cli publish \
  --channel dev --version 0.1.0 --platform linux-x86_64 \
  --adapter github --adapter-arg repo=aware-org/aware-cli --adapter-arg tag=aware-cli/dev/0.1.0

# Dispatch registered workflows (e.g., regenerate rule versions)
uv run --project tools/release-pipeline release-pipeline workflow list
uv run --project tools/release-pipeline release-pipeline workflow trigger \
  --workflow cli-rules-version \
  --dry-run

# Enumerate and run composite pipelines
uv run --project tools/release-pipeline release-pipeline pipeline list
uv run --project tools/release-pipeline release-pipeline pipeline run \
  --pipeline cli-bundle \
  --input channel=dev \
  --input version=0.1.0 \
  --input wheel=dist/aware_cli-0.1.0-py3-none-any.whl

# Complete release (bundle + rules + tests + workflow + publish)
uv run --project tools/release-pipeline release-pipeline pipeline run \
  --pipeline cli-release-e2e \
  --input channel=dev \
  --input version=0.1.0 \
  --input skip-tests=true \
  --input skip-workflow=true \
  --input skip-publish=true

# (The pipeline builds the aware-cli wheel automatically via `uv build`.)

# Optional knobs: supply extra wheels, skip build, or extend uv build flags
uv run --project tools/release-pipeline release-pipeline pipeline run \
  --pipeline cli-release-e2e \
  --input channel=dev \
  --input version=0.1.0 \
  --input wheel=dist/aware_terminal-0.2.0-py3-none-any.whl \
  --input skip-build=true

# Generate rule versions directly via pipeline helper
uv run --project tools/release-pipeline release-pipeline rules render \
  --version 0.8.3 \
  --rules-root docs/rules \
  --manifest build/rule-manifest.json

# Note: GitHub workflows that call aware-cli should run `uv sync --project tools/cli`
# before invoking release commands to ensure dependencies (pydantic, etc.) are available.

# The CLI loads <repo>/.env automatically if present (temporary convenience until aware-env rollout).
# Combine with `aware-cli release secrets-list` to verify token sources (env, dotenv, etc.).
```

See `docs/2025-10-24T23-55-00Z-release-pipeline-overview.md` for full details.
