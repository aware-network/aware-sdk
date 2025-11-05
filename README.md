# aware-sdk

`aware-sdk` is the baseline distribution for the Aware stack. It packages the
CLI-first infrastructure that Release, Terminal, and future environment
features share: automated publishing, manifest-driven testing, filesystem
indexing, and the terminal runtime. Install it to recreate the same tooling the
Aware release pipeline and Studio builds consume.

## Installation

```bash
pip install aware-sdk
```

Python 3.12 or newer is required.

For CI parity and local testing install the optional `test` extra, which pulls
in pytest and async fixtures used by the bundled suites:

```bash
pip install "aware-sdk[test]"
```

The SDK installs the following packages (with compatible versions):

- [`aware-release`](https://pypi.org/project/aware-release/) — bundle builder,
  manifest tooling, and workflow helpers.
- [`aware-test-runner`](https://pypi.org/project/aware-test-runner/) — manifest-
  driven test orchestration.
- [`aware-file-system`](https://pypi.org/project/aware-file-system/) —
  filesystem watcher/indexer used by the CLI and SDK.
- [`aware-terminal`](https://pypi.org/project/aware-terminal/) — terminal daemon
  and PTY orchestration used by Studio.
- [`aware-terminal-providers`](https://pypi.org/project/aware-terminal-providers/)
  — provider registry and workflows for Terminal automation.

## Running the OSS test suites

`aware-test-runner` expects callers to provide a manifest explicitly. The SDK
bundles the canonical OSS definitions under
`aware_sdk/configs/manifests/oss/`. Point
`AWARE_TEST_RUNNER_MANIFEST_DIRS` (or `--manifest-file`) at that directory when
you want to run the published suite matrix:

```bash
MANIFEST=$(python - <<'PY'
import importlib.resources as res
print(res.files('aware_sdk.configs.manifests.oss') / 'manifest.json')
PY
)
aware-tests --manifest-file "$MANIFEST" --stable --no-warnings
```

Internal overlays live in the monorepo under `configs/manifests/` and can be
composed the same way.

## CLI helper

The package exposes a lightweight `aware-sdk` CLI that reports the installed
versions of the bundled components:

```bash
$ aware-sdk
{
  "aware_sdk": "0.6.1",
  "aware_release": "0.1.2",
  "aware_test_runner": "0.2.0",
  "aware_file_system": "0.1.1",
  "aware_terminal": "0.3.3"
}
```

(Version numbers will reflect the installed releases.)

Use this command in CI or local scripts to verify that your environment is
synchronised with the recommended versions.

## Usage

Once `aware-sdk` is installed you can immediately invoke the bundled tooling.
Examples:

```bash
# Build a release bundle
aware-release bundle --help

# Run the curated OSS test suites
aware-tests --manifest-file "$MANIFEST" --stable --no-warnings

# Start the filesystem watcher
python -m aware_file_system.examples.watch_docs
```

Refer to the individual package documentation for detailed usage.

## Versioning & changelog

`aware-sdk` itself contains only the helper CLI, metadata, and curated
configuration (manifests, panel definitions, docs). All functional updates live
in the underlying packages. Each SDK release documents the expected versions so
clean-room installs stay in sync with the public pipeline.

## What comes next

The current SDK focuses on infrastructure. Upcoming milestones add the
environment/kernel objects (rules, ACL, CLI object graph) so third parties can
layer their own environments on top of the same CLI-first foundation. Follow
the changelog for progress.

## License

Distributed under the MIT License. See `LICENSE` for details.
