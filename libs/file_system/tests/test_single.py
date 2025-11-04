#!/usr/bin/env python3
"""
Single test for debugging FileSystemWatcher.
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
import sys
import os
import logging

import pytest

pytestmark = pytest.mark.skip(reason="Manual single-file watcher debugging harness.")

# Setup logging
logging.basicConfig(level=logging.DEBUG)

from aware_file_system.config import Config, FileSystemConfig
from aware_file_system.watcher import FileSystemWatcher, FileChangeEvent
from aware_file_system.models import ChangeType


async def test_file_creation():  # pragma: no cover - manual harness
    """Test detection of newly created files."""
    print("Testing file creation detection...")

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp(prefix="test_watcher_"))
    print(f"Test directory: {temp_dir}")

    try:
        # Create watcher
        config = Config(file_system=FileSystemConfig(root_path=str(temp_dir), generate_tree=False))
        watcher = FileSystemWatcher(config, poll_interval=1.0)

        # Track events
        events_received = []

        async def handler(event: FileChangeEvent):
            events_received.append(event)
            print(f"  🔔 Event: {event.change_type.name} - {event.path}")

        watcher.add_event_handler(handler)

        # Start watcher
        await watcher.start()
        print(f"✅ Watcher started")
        print(f"  Initial files tracked: {len(watcher._last_state)}")
        print(f"  Initial state: {list(watcher._last_state.keys())}")

        # Wait for initial scan
        await asyncio.sleep(0.5)

        # Create new file
        test_file = temp_dir / "test_new.txt"
        test_file.write_text("Hello from Python FileSystemWatcher!")
        print(f"📝 Created file: {test_file.name}")

        # Wait for detection
        print("⏳ Waiting for detection...")
        await asyncio.sleep(3.0)

        print(f"  Files tracked after: {len(watcher._last_state)}")
        print(f"  Current state: {list(watcher._last_state.keys())}")
        print(f"  Total events received: {len(events_received)}")

        # Check results
        if len(events_received) > 0:
            print("✅ File change detected!")
            for e in events_received:
                print(f"   - {e.change_type.name}: {e.path}")
            return True
        else:
            print("❌ No events detected")
            return False

    finally:
        # Cleanup
        await watcher.stop()
        print("🧹 Cleanup complete")
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    result = asyncio.run(test_file_creation())
    sys.exit(0 if result else 1)
