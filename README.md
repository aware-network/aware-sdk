# aware-sdk

`aware-sdk` is the convenience bundle for installing the Aware release toolchain.
It pulls in the published `aware-release`, `aware-test-runner`, and
`aware-file-system` packages so you can bootstrap an environment with a single
`pip install`.

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

For Terminal integrations install the optional `terminal` extra, which bundles
the daemon and provider registry published by the release pipeline:

```bash
pip install "aware-sdk[terminal]"
```

This command installs the following packages (with compatible versions):

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

## CLI helper

The package exposes a lightweight `aware-sdk` CLI that reports the installed
versions of the bundled components:

```bash
$ aware-sdk
{
  "aware_sdk": "0.0.0",
  "aware_release": "0.1.2",
  "aware_test_runner": "0.1.2",
  "aware_file_system": "0.1.0"
}
```

(Version numbers will reflect the installed releases.)

Use this command in CI or local scripts to verify that your environment is
synchronised with the recommended versions.

## Usage

Once `aware-sdk` is installed you can immediately invoke the underlying
packages. Common examples:

```bash
# Build a release bundle
aware-release bundle --help

# Run the curated OSS test suites
aware-tests --manifest oss --stable --no-warnings

# Start the filesystem watcher
python -m aware_file_system.examples.watch_docs
```

Refer to the individual package documentation for detailed usage.

## Versioning & changelog

`aware-sdk` itself contains only the helper CLI and metadata. All functional
updates happen in the underlying packages. Each release of the SDK documents
which versions of the bundled packages it expects.

## License

Distributed under the MIT License. See `LICENSE` for details.
