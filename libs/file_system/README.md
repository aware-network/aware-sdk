# aware-file-system

`aware-file-system` is the change-detection layer behind `aware-cli` and the upcoming
`aware-sdk`. It watches repository folders, persists lightweight indexes, and emits
structured events so agents and automation can safely treat the filesystem as a
source of truth.

## Highlights

- **Recursive watcher** – polls directories, classifies create/update/delete events,
  and normalises them into JSON-ready payloads.
- **Index snapshots** – builds MsgPack-backed caches to accelerate large tree
  scans and cold starts.
- **Pluggable handlers** – send events to aware-cli’s summary state, your own async
  consumers, or a queue service by registering callbacks.
- **Pure Python** – easy to embed inside CI, long-running daemons, or custom tools.

## Installation

```bash
pip install aware-file-system
```

Requires Python 3.12 or newer.

## Quick start

```python
import asyncio
from aware_file_system.config import Config, FileSystemConfig
from aware_file_system.models import ChangeType
from aware_file_system.watcher.file_system_watcher import FileSystemWatcher

async def main() -> None:
    config = Config(file_system=FileSystemConfig(root_path="docs/projects"))
    watcher = FileSystemWatcher(config, poll_interval=2.0)

    def handle(event) -> None:
        if event.change_type is ChangeType.MODIFIED:
            print(f"{event.path} updated ({event.checksum.sha256[:8]})")

    watcher.add_event_handler(handle)

    await watcher.start()
    try:
        await asyncio.sleep(10)
    finally:
        await watcher.stop()

asyncio.run(main())
```

### Integrating with aware-cli

```bash
aware-cli summary \
  --project aware-sdk \
  --task cli-release-bundles \
  --watch-root docs/projects
```

The CLI wires `aware-file-system` under the hood to stream change events into its
summary state. You can reuse the same configuration helpers (environment variables,
YAML config) to point at other workspaces or embed the watcher inside your tooling.

## Configuration reference

- `AWARE_FILE_SYSTEM_ROOT` – override the root directory that should be scanned.
- `AWARE_FILE_SYSTEM_POLL_INTERVAL` – polling cadence in seconds (default: 2.0).
- `AWARE_FILE_SYSTEM_CACHE_DIR` – location for MsgPack indexes (default: `.aware/fs`).
- `aware_file_system.config.Config` – Python API with sensible defaults and
  room for custom callbacks.

## Testing

Run the suite from the repository root:

```bash
uv run --project libs/file_system pytest
```

## Roadmap

- Optional native backends (inotify/FSEvents) for lower latency on supported
  platforms.
- Batched event delivery for agent-friendly payloads.
- Additional helpers to serialise change events into the Aware receipt format.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

Distributed under the MIT License. See [LICENSE](LICENSE).
