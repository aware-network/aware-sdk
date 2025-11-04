from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout

from aware_release.cli import release as release_cli

from .test_bundle_builder import _create_wheel  # reuse helper


def _run_cli(argv: list[str]) -> dict:
    buffer = StringIO()
    with redirect_stdout(buffer):
        release_cli.main(argv)
    return json.loads(buffer.getvalue())


def test_cli_bundle_command(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "aware_cli-0.1.0-py3-none-any.whl"
    _create_wheel(wheel, "aware_cli", "0.1.0")

    payload = _run_cli(
        [
            "bundle",
            "--channel",
            "dev",
            "--version",
            "0.1.0",
            "--platform",
            "linux-x86_64",
            "--wheel",
            str(wheel),
            "--workspace-root",
            str(tmp_path),
        ]
    )

    archive_path = Path(payload["archive_path"])
    assert archive_path.exists()
    manifest = json.loads(Path(payload["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["channel"] == "dev"
