# aware-release

`aware-release` packages the release automation used by aware-cli, Studio, and pipeline tooling. It assembles bundle artefacts, generates manifests, and publishes archives through a consistent, schema-validated interface.

## Install

```bash
pip install aware-release
```

The CLI executable `aware-release` is added to your PATH. The library targets Python 3.12+.

## Features

- Build aware-cli bundle directories and archives (zip/tar) without baking a virtualenv.
- Generate manifest metadata backed by Pydantic models for deterministic validation.
- Provide publishing adapters (command, GitHub Releases, S3) that emit structured receipts.
- Supply helper workflows for rule versioning so CLI bundles ship with current documentation.
- Share a reusable secret registry with resolver diagnostics for environment variables and `.env` files.

## Quick Start

Run the bundled CLI help to explore subcommands:

```bash
aware-release --help
aware-release bundle --help
```

Bundle an aware-cli wheel:

```bash
aware-release bundle \
  --channel dev \
  --version 0.1.0 \
  --platform linux-x86_64 \
  --wheel dist/aware_cli-0.1.0-py3-none-any.whl
```

Generate publish metadata (dry-run by default):

```bash
aware-release publish \
  --manifest releases/dev/0.1.0/linux-x86_64/manifest.json \
  --archive releases/dev/0.1.0/linux-x86_64/bundle.tar.gz \
  --adapter command \
  --adapter-command "echo upload {archive}"
```

## Secret diagnostics

`aware-release` powers the shared secret registry used by aware-cli and the release pipeline. Tokens may come from process environment variables, `.env` files, or custom resolvers registered via `aware_release.secrets.register_resolver()`. Inspect the current state with:

```bash
uv run --project tools/cli aware-cli release secrets-list
```

Each entry reports whether the secret is present, the resolver (`env`, `dotenv@...`, etc.), and any resolver metadata (e.g., `.env` paths or parse warnings). When a workflow token is missing, the error message now lists the resolvers that were checked and points back to `secrets-list` for remediation. Programmatic callers can use `aware_release.resolve_secret_info("GH_TOKEN_RELEASE")` to obtain the same diagnostics.

## Python Usage

```python
from pathlib import Path

from aware_release.bundle.builder import BundleBuilder, BundleConfig

builder = BundleBuilder()
config = BundleConfig(
    channel="dev",
    version="0.1.0",
    platform="linux-x86_64",
    source_wheels=[Path("dist/aware_cli-0.1.0-py3-none-any.whl")],
    output_dir=Path("releases"),
)
bundle_path = builder.build(config)
print(bundle_path)
```

## Release automation

The release pipeline bundles build/test/publish flows so agents can ship packages with a single command. Example (dry run):

```bash
uv run --project tools/release-pipeline release-pipeline pipeline run \
  --pipeline tests-release \
  --input bump=patch \
  --input dry-run=true \
  --input skip-workflow=true
```

Remove `dry-run`/`skip-workflow` once the build succeeds to trigger the GitHub `publish-aware-test-runner` workflow and PyPI publish.

## Rule Version Automation

```bash
aware-release rules render \
  --rules-root docs/rules \
  --manifest build/rule-manifest.json
```

This wrapper regenerates rule versions (mirroring `aware-cli docs render --target rules --write-version`) and emits a manifest for downstream packaging.


## Publishing

To publish to PyPI using the shared workflow:

```bash
# Dry run via release-pipeline helper
uv run --project tools/release-pipeline release-pipeline cli aware-release publish-pypi --dry-run

# Then trigger GitHub Action (Publish aware-release) with dry_run=false
```

The workflow uses trusted publishers (OIDC), so no persistent PyPI token is required.
## CI / Tests

Run the test suite with:

```bash
uv run --project tools/release pytest
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release notes.

## License

MIT © 2025 AWARE
```

All commands emit structured JSON for automation pipelines.

## Rule version automation

aware-cli owns rule rendering, so every release pipeline should regenerate the versioned rule set before building bundles. The new `--write-version` workflow turns templates into versioned/current copies and emits a manifest for downstream packaging.

Minimal example (run inside the aware repository):

```bash
export AWARE_RULES_ROOT=${AWARE_RULES_ROOT:-docs/rules}
CLI_VERSION=$(uv run --project tools/cli python -c "import aware_cli; print(aware_cli.__version__)")

# Iterate over the rule ids we ship (list_rules() may be used for automation)
for rule_id in 02-task-01-lifecycle 02-task-03-change-tracking 04-agent-01-memory-hierarchy; do
  uv run --project tools/cli aware-cli docs render \
    --target rules \
    --rule "$rule_id" \
    --write-version \
    --cli-version "$CLI_VERSION" \
    --rules-root "$AWARE_RULES_ROOT" \
    --update-current copy \
    --json-output build/rule-manifest.json
done
```

The above command:

- Loads each template from `$AWARE_RULES_ROOT/templates/<rule>.md` and renders fresh fragments.
- Writes versioned copies under `$AWARE_RULES_ROOT/versions/<cli-version>/` with frontmatter containing `aware_cli_version`, `generated_at`, and `source_template`.
- Copies the version into `$AWARE_RULES_ROOT/current/` (use `--update-current symlink` if the platform supports symlinks).
- Appends a JSON manifest entry to `build/rule-manifest.json`; the release scripts can read this manifest to stage artefacts or publish alongside the bundle.

For more dynamic pipelines, you can gather rule identifiers programmatically:

```bash
uv run --project tools/cli python - <<'PY'
from aware_cli.registry.rules import list_rules
for rule in list_rules():
    print(rule.id)
PY
```

Always regenerate rules before invoking `aware-release bundle` so the archive includes up-to-date `rules/versions/<cli-version>` and `rules/current`. External consumers (e.g., aware-sdk) can call the same CLI command by pointing `--rules-root` at their unpacked package data.

To trigger the regeneration workflow from automation, use the release-pipeline registry slug:

```bash
uv run --project tools/release-pipeline release-pipeline workflow trigger \
  --workflow cli-rules-version \
  --dry-run

You can also invoke rule regeneration directly via the pipeline helper:

```bash
uv run --project tools/release-pipeline release-pipeline rules render \
  --rules-root docs/rules \
  --manifest build/rule-manifest.json
```
```

The corresponding GitHub Actions workflow lives at `.github/workflows/cli-rules-version.yml` and uploads the refreshed manifest and rule directories as artefacts.

## Contributing
- Keep code/tests/docs aligned per `docs/BEST_PRACTICES.md`.
- Update `CHANGELOG.md` whenever modifying public APIs.
- Run `uv run pytest` before submitting changes.
