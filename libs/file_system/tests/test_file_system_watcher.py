import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Awaitable

import pytest
import pytest_asyncio

from aware_file_system.config import Config, FileSystemConfig
from aware_file_system.models import ChangeType
from aware_file_system.watcher import FileChangeEvent, FileSystemWatcher

POLL_INTERVAL = 0.1
SLEEP_PADDING = POLL_INTERVAL * 4


@pytest_asyncio.fixture
async def temp_dir():
    path = Path(tempfile.mkdtemp(prefix="afs_watcher_"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest_asyncio.fixture
async def watcher(temp_dir: Path):
    config = Config(file_system=FileSystemConfig(root_path=str(temp_dir), generate_tree=False, export_json=False))
    watcher = FileSystemWatcher(config, poll_interval=POLL_INTERVAL)
    try:
        yield watcher
    finally:
        if watcher._is_running:
            await watcher.stop()


def _collect_events(watcher: FileSystemWatcher) -> list[FileChangeEvent]:
    events: list[FileChangeEvent] = []

    async def handler(event: FileChangeEvent) -> None:
        events.append(event)

    watcher.add_event_handler(handler)
    return events


async def _exercise_watcher(
    watcher: FileSystemWatcher,
    action: Callable[[], Awaitable[None] | None],
) -> list[FileChangeEvent]:
    events = _collect_events(watcher)
    await watcher.start()
    await asyncio.sleep(POLL_INTERVAL)
    result = action()
    if asyncio.iscoroutine(result):
        await result
    await asyncio.sleep(SLEEP_PADDING)
    await watcher.stop()
    return events


class TestFileSystemWatcher:
    @pytest.mark.asyncio
    async def test_initialization(self, watcher: FileSystemWatcher, temp_dir: Path) -> None:
        assert watcher.root_path == temp_dir
        assert watcher.poll_interval == POLL_INTERVAL
        assert not watcher._is_running

    @pytest.mark.asyncio
    async def test_start_stop(self, watcher: FileSystemWatcher) -> None:
        await watcher.start()
        assert watcher._is_running
        await watcher.stop()
        assert not watcher._is_running

    @pytest.mark.asyncio
    async def test_detect_creation(self, watcher: FileSystemWatcher, temp_dir: Path) -> None:
        file_path = temp_dir / "created.txt"
        events = await _exercise_watcher(watcher, lambda: file_path.write_text("hello"))
        created = [e for e in events if e.change_type == ChangeType.ADDED]
        assert len(created) == 1
        assert created[0].path == "created.txt"

    @pytest.mark.asyncio
    async def test_detect_modification(self, watcher: FileSystemWatcher, temp_dir: Path) -> None:
        file_path = temp_dir / "modified.txt"
        file_path.write_text("initial")

        events = await _exercise_watcher(watcher, lambda: file_path.write_text("updated"))
        modified = [e for e in events if e.change_type == ChangeType.MODIFIED]
        assert len(modified) == 1
        assert modified[0].path == "modified.txt"

    @pytest.mark.asyncio
    async def test_detect_deletion(self, watcher: FileSystemWatcher, temp_dir: Path) -> None:
        file_path = temp_dir / "deleted.txt"
        file_path.write_text("bye")

        events = await _exercise_watcher(watcher, lambda: file_path.unlink())
        deleted = [e for e in events if e.change_type == ChangeType.DELETED]
        assert len(deleted) == 1
        assert deleted[0].path == "deleted.txt"

    @pytest.mark.asyncio
    async def test_ignore_binary_extensions(self, watcher: FileSystemWatcher, temp_dir: Path) -> None:
        binary = temp_dir / "image.png"
        text = temp_dir / "note.txt"

        events = await _exercise_watcher(
            watcher,
            lambda: (
                binary.write_bytes(b"PNG"),
                text.write_text("visible"),
            ),
        )
        created = [e.path for e in events if e.change_type == ChangeType.ADDED]
        assert created == ["note.txt"]

    @pytest.mark.asyncio
    async def test_ignore_system_directories(self, watcher: FileSystemWatcher, temp_dir: Path) -> None:
        def action():
            git = temp_dir / ".git"
            git.mkdir()
            (git / "config").write_text("core")
            (temp_dir / "docs").mkdir()
            (temp_dir / "docs" / "file.md").write_text("doc")

        events = await _exercise_watcher(watcher, action)
        created = [e.path for e in events if e.change_type == ChangeType.ADDED]
        assert created == ["docs/file.md"]

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, watcher: FileSystemWatcher, temp_dir: Path) -> None:
        handler1_events: list[FileChangeEvent] = []
        handler2_events: list[FileChangeEvent] = []

        async def handler1(event: FileChangeEvent) -> None:
            handler1_events.append(event)

        async def handler2(event: FileChangeEvent) -> None:
            handler2_events.append(event)

        watcher.add_event_handler(handler1)
        watcher.add_event_handler(handler2)

        file_path = temp_dir / "multi.txt"
        events = await _exercise_watcher(watcher, lambda: file_path.write_text("multi"))

        assert events
        assert handler1_events
        assert handler2_events

    @pytest.mark.asyncio
    async def test_stats(self, watcher: FileSystemWatcher, temp_dir: Path) -> None:
        stats = watcher.get_stats()
        assert stats["root_path"] == str(temp_dir)
        assert not stats["is_running"]

        await watcher.start()
        await asyncio.sleep(POLL_INTERVAL)
        stats = watcher.get_stats()
        assert stats["is_running"]

        await watcher.stop()
        stats = watcher.get_stats()
        assert not stats["is_running"]
