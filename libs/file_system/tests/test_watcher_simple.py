#!/usr/bin/env python3
"""
Simple test for FileSystemWatcher without pytest.
"""

import asyncio
import tempfile
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.skip(reason="Manual integration checks for FileSystemWatcher; kept for local debugging.")

from aware_file_system.config import Config, FileSystemConfig
from aware_file_system.watcher import FileSystemWatcher, FileChangeEvent, RepositoryFileSystemWatcher
from aware_file_system.models import ChangeType


async def test_file_creation():  # pragma: no cover - manual harness
    """Test detection of newly created files."""
    print("Testing file creation detection...")

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp(prefix="test_watcher_"))

    try:
        # Create watcher
        config = Config(file_system=FileSystemConfig(root_path=str(temp_dir), generate_tree=False))
        watcher = FileSystemWatcher(config, poll_interval=1.0)

        # Track events
        events_received = []

        async def handler(event: FileChangeEvent):
            events_received.append(event)
            print(f"  Event: {event.change_type.name} - {event.path}")

        watcher.add_event_handler(handler)

        # Start watcher
        await watcher.start()
        print(f"  Watcher started for {temp_dir}")
        print(f"  Initial files tracked: {len(watcher._last_state)}")

        # Wait for initial scan
        await asyncio.sleep(0.5)

        # Create new file
        test_file = temp_dir / "test_new.txt"
        test_file.write_text("Hello from Python FileSystemWatcher!")
        print(f"  Created file: {test_file.name}")

        # Wait for detection
        await asyncio.sleep(2.5)

        print(f"  Files tracked after: {len(watcher._last_state)}")
        print(f"  Total events received: {len(events_received)}")

        # Check results
        creation_events = [e for e in events_received if e.change_type == ChangeType.ADDED]
        if len(creation_events) == 1:
            print("  ✅ File creation detected successfully!")
            return True
        else:
            print(f"  ❌ Expected 1 creation event, got {len(creation_events)}")
            if events_received:
                print(f"  All events: {[(e.change_type.name, e.path) for e in events_received]}")
            return False

    finally:
        # Cleanup
        await watcher.stop()
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_file_modification():  # pragma: no cover - manual harness
    """Test detection of file modifications."""
    print("Testing file modification detection...")

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp(prefix="test_watcher_"))

    try:
        # Create initial file
        test_file = temp_dir / "test_modify.txt"
        test_file.write_text("Initial content")

        # Create watcher
        config = Config(file_system=FileSystemConfig(root_path=str(temp_dir), generate_tree=False))
        watcher = FileSystemWatcher(config, poll_interval=1.0)

        # Track events
        events_received = []

        async def handler(event: FileChangeEvent):
            events_received.append(event)
            print(f"  Event: {event.change_type.name} - {event.path}")

        watcher.add_event_handler(handler)

        # Start watcher
        await watcher.start()
        print(f"  Watcher started for {temp_dir}")

        # Wait for initial scan
        await asyncio.sleep(0.5)
        events_received.clear()  # Clear initial events

        # Modify file
        test_file.write_text("Modified content!")
        print(f"  Modified file: {test_file.name}")

        # Wait for detection
        await asyncio.sleep(2.0)

        # Check results
        mod_events = [e for e in events_received if e.change_type == ChangeType.MODIFIED]
        if len(mod_events) >= 1:
            print("  ✅ File modification detected successfully!")
            return True
        else:
            print(f"  ❌ Expected modification event, got {len(mod_events)}")
            return False

    finally:
        # Cleanup
        await watcher.stop()
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_file_deletion():  # pragma: no cover - manual harness
    """Test detection of file deletions."""
    print("Testing file deletion detection...")

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp(prefix="test_watcher_"))

    try:
        # Create initial file
        test_file = temp_dir / "test_delete.txt"
        test_file.write_text("To be deleted")

        # Create watcher
        config = Config(file_system=FileSystemConfig(root_path=str(temp_dir), generate_tree=False))
        watcher = FileSystemWatcher(config, poll_interval=1.0)

        # Track events
        events_received = []

        async def handler(event: FileChangeEvent):
            events_received.append(event)
            print(f"  Event: {event.change_type.name} - {event.path}")

        watcher.add_event_handler(handler)

        # Start watcher
        await watcher.start()
        print(f"  Watcher started for {temp_dir}")

        # Wait for initial scan
        await asyncio.sleep(0.5)
        events_received.clear()  # Clear initial events

        # Delete file
        test_file.unlink()
        print(f"  Deleted file: {test_file.name}")

        # Wait for detection
        await asyncio.sleep(2.0)

        # Check results
        del_events = [e for e in events_received if e.change_type == ChangeType.DELETED]
        if len(del_events) == 1:
            print("  ✅ File deletion detected successfully!")
            return True
        else:
            print(f"  ❌ Expected 1 deletion event, got {len(del_events)}")
            return False

    finally:
        # Cleanup
        await watcher.stop()
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_gitignore_filtering():  # pragma: no cover - manual harness
    """Test GitIgnore-style filtering."""
    print("Testing GitIgnore-style filtering...")

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp(prefix="test_watcher_"))

    try:
        # Create watcher
        config = Config(file_system=FileSystemConfig(root_path=str(temp_dir), generate_tree=False))
        watcher = FileSystemWatcher(config, poll_interval=1.0)

        # Track events
        events_received = []

        async def handler(event: FileChangeEvent):
            events_received.append(event)
            print(f"  Event: {event.change_type.name} - {event.path}")

        watcher.add_event_handler(handler)

        # Start watcher
        await watcher.start()
        print(f"  Watcher started for {temp_dir}")

        # Wait for initial scan
        await asyncio.sleep(0.5)
        events_received.clear()

        # Create files that should be ignored
        (temp_dir / ".aware").mkdir()
        (temp_dir / ".aware" / "blob.dat").write_bytes(b"blob")
        (temp_dir / "test.pyc").write_bytes(b"pyc")
        (temp_dir / "image.png").write_bytes(b"PNG")

        # Create file that should be detected
        (temp_dir / "code.py").write_text("print('hello')")

        print("  Created: .aware/blob.dat (should ignore)")
        print("  Created: test.pyc (should ignore)")
        print("  Created: image.png (should ignore)")
        print("  Created: code.py (should detect)")

        # Wait for detection
        await asyncio.sleep(2.0)

        # Check only code.py was detected
        creation_events = [e for e in events_received if e.change_type == ChangeType.ADDED]
        detected_files = [e.path for e in creation_events]

        if "code.py" in detected_files and len(detected_files) == 1:
            print("  ✅ GitIgnore filtering working correctly!")
            return True
        else:
            print(f"  ❌ Expected only 'code.py', got: {detected_files}")
            return False

    finally:
        # Cleanup
        await watcher.stop()
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_repository_integration():  # pragma: no cover - manual harness
    """Test RepositoryFileSystemWatcher integration."""
    print("Testing Repository integration...")

    # Mock repository
    class MockRepository:
        def __init__(self):
            self.name = "test-repo"
            self.workspace_root = tempfile.mkdtemp(prefix="test_repo_")

    repo = MockRepository()

    try:
        # Create watcher
        repo_watcher = RepositoryFileSystemWatcher(repo, poll_interval=1.0)

        # Test stats
        stats = repo_watcher.get_stats()
        print(f"  Repository: {stats['repository_name']}")
        print(f"  Workspace: {stats['repository_workspace']}")

        # Start and test
        await repo_watcher.start()
        print("  ✅ Repository watcher started successfully!")

        # Create a test file
        test_file = Path(repo.workspace_root) / "test.txt"
        test_file.write_text("Repository test")

        # Wait for detection
        await asyncio.sleep(2.0)

        # Stop
        await repo_watcher.stop()
        print("  ✅ Repository watcher stopped successfully!")

        return True

    finally:
        # Cleanup
        shutil.rmtree(repo.workspace_root, ignore_errors=True)


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Python FileSystemWatcher Tests")
    print("=" * 60)

    results = []

    # Run tests
    results.append(await test_file_creation())
    results.append(await test_file_modification())
    results.append(await test_file_deletion())
    results.append(await test_gitignore_filtering())
    results.append(await test_repository_integration())

    # Summary
    print("=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)

    if passed == total:
        print(f"✅ All {total} tests passed!")
    else:
        print(f"❌ {passed}/{total} tests passed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
