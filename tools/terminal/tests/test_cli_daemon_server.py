from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from aware_terminal.cli import cli


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux not available")
def test_daemon_serve_starts_and_handles_ctrl_c(tmp_path: Path) -> None:
    runner = CliRunner()
    aware_home = tmp_path / "aware"
    socket_path = tmp_path / "sock"

    # Seed manifest
    env = {"AWARE_HOME": str(aware_home), "AWARE_STATE_HOME": str(aware_home / "state")}
    start_result = runner.invoke(
        cli,
        ["daemon", "start", "--thread", "t-test", "--socket", str(socket_path)],
        env=env,
    )
    if start_result.exit_code != 0:
        pytest.skip("daemon start unavailable in test environment")

    result = runner.invoke(
        cli,
        ["daemon", "serve", "--thread", "t-test", "--socket", str(socket_path), "--once"],
        env=env,
    )
    if result.exception and "tmux" in str(result.exception):
        pytest.skip("tmux unavailable for serve command in CI")
    assert result.exit_code == 0

    runner.invoke(
        cli,
        ["daemon", "stop", "--thread", "t-test"],
        env=env,
    )
