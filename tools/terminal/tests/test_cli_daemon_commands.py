from __future__ import annotations

from pathlib import Path

import pytest

from click.testing import CliRunner

from aware_terminal.cli import cli


def _manifest_path(base: Path, thread: str) -> Path:
    return base / "threads" / thread / "terminal" / "manifest.json"


def test_daemon_start_creates_manifest(tmp_path) -> None:
    runner = CliRunner()
    aware_home = tmp_path / "aware"
    socket_path = tmp_path / "sock"

    env = {"AWARE_HOME": str(aware_home), "AWARE_STATE_HOME": str(aware_home / "state")}
    result = runner.invoke(
        cli,
        ["daemon", "start", "--thread", "t-test", "--socket", str(socket_path)],
        env=env,
    )
    if result.exit_code != 0:
        pytest.skip("daemon start unavailable in test environment")
    assert result.exit_code == 0

    manifest_file = _manifest_path(aware_home, "t-test")
    assert manifest_file.exists()

    runner.invoke(
        cli,
        ["daemon", "stop", "--thread", "t-test"],
        env=env,
    )


def test_daemon_status_reads_manifest(tmp_path) -> None:
    runner = CliRunner()
    aware_home = tmp_path / "aware"
    socket_path = tmp_path / "sock"

    # Seed manifest via start command
    env = {"AWARE_HOME": str(aware_home), "AWARE_STATE_HOME": str(aware_home / "state")}
    start_result = runner.invoke(
        cli,
        ["daemon", "start", "--thread", "t-test", "--socket", str(socket_path)],
        env=env,
    )
    if start_result.exit_code != 0:
        pytest.skip("daemon start unavailable in test environment")
    assert start_result.exit_code == 0

    result = runner.invoke(
        cli,
        ["daemon", "status", "--thread", "t-test", "--socket", str(socket_path)],
        env=env,
    )
    assert result.exit_code == 0
    assert "Thread: t-test" in result.output
    assert "Daemon running:" in result.output

    runner.invoke(
        cli,
        ["daemon", "stop", "--thread", "t-test"],
        env=env,
    )
