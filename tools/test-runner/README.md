# aware-test-runner

`aware-test-runner` packages the manifest-driven test orchestration we use across the
Aware platform. It exposes a tiny CLI (`aware-tests`) that mirrors our CI layout so
contributors can run the same curated suites locally or inside automation.

The runner no longer bundles a default manifest. Always supply a manifest
identifier or file path explicitly. The **aware-sdk** distribution publishes the
OSS manifests under `aware_sdk/configs/manifests/oss`, and internal overlays live
in the monorepo under `configs/manifests/internal`.

## Key capabilities

- Declarative manifests (`stable.json`, `runtime.json`) that describe suites,
  marks, and pytest flags.
- CLI helpers to list suites, execute a subset, or hand over execution to pytest.
- Environment variable overrides so CI can provide a different manifest directory
  without modifying the command line.
- Ready-to-extend extras (e.g. `internal`, `flutter`) for optional dependencies.

## Installation

```bash
pip install aware-test-runner
```

Requires Python 3.10+. The package works with both `pip` and `uv`. Extras will land
once the internal split for our larger matrix is stabilised.

## Quick start

Point the runner at your manifest directory (for the OSS bundle bundled with
aware-sdk use `aware_sdk/configs/manifests`):

```bash
export AWARE_TEST_RUNNER_MANIFEST_DIRS=$PWD/aware_sdk/configs/manifests
```

Run the OSS stable suites:

```bash
aware-tests --manifest oss --stable
```

Discover available suites:

```bash
aware-tests --list
```

Execute a focused set and forward options to pytest:

```bash
aware-tests --suites kernel -- -k "smoke and not slow" --maxfail=1
```

## Manifest selection

Manifests can be controlled through identifiers, paths, or environment variables.

| Mechanism | Example |
| --- | --- |
| Named manifest | `aware-tests --manifest internal` |
| Manifest file | `aware-tests --manifest-file aware_sdk/configs/manifests/oss/manifest.json` |
| Directory search path | `AWARE_TEST_RUNNER_MANIFEST_DIRS=$PWD/aware_sdk/configs/manifests:$PWD/configs/manifests` |
| Explicit identifier (env) | `AWARE_TEST_RUNNER_MANIFEST=runtime` |
| Override file (env) | `AWARE_TEST_RUNNER_MANIFEST_FILE=/tmp/runtime.json` |

The internal suite overlays live under `configs/manifests/internal/`; include
that directory in `AWARE_TEST_RUNNER_MANIFEST_DIRS` when targeting private suites.

Each manifest can inherit from another via an `extends` field, allowing the internal
configuration to re-use the OSS baseline.

## CI usage

Add a job that configures the manifest directory and runs the stable matrix:

```yaml
- name: Run OSS suites
  run: |
    export AWARE_TEST_RUNNER_MANIFEST_DIRS=$GITHUB_WORKSPACE/aware_sdk/configs/manifests
    aware-tests --manifest oss --stable --no-warnings

Internal jobs can point the same variable at `$GITHUB_WORKSPACE/configs/manifests`
to pick up the private overlays.
```

For larger installations we recommend pinning the manifest alongside the workspace
so agents and humans see the exact same suite definitions.

## Roadmap

- Publish optional extras for internal-only dependencies.
- Ship pre-built manifest bundles targeting different providers (CI, Studio, SDK).
- Expose a Python API for embedding manifests inside other orchestration layers.

## Support

- OSS quickstart: this README.
- Release automation: tracked under
  `docs/projects/aware-developer-tools/tasks/aware-test-runner-tooling/`.
- Legacy compatibility: importing `aware_tests` still works but emits a notice
  pointing to `aware_test_runner`.

Bug reports and suggestions are welcome via issues in `aware-network/aware`.

## License

Distributed under the MIT License. See `LICENSE` for details.
