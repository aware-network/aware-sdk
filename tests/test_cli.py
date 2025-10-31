from __future__ import annotations

import json

import aware_sdk
from aware_sdk import cli


def test_version_string_present() -> None:
    assert isinstance(aware_sdk.__version__, str)
    assert aware_sdk.__version__


def test_cli_info_outputs_json(capsys) -> None:
    exit_code = cli.info()
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert "aware_sdk" in payload
    assert "aware_release" in payload
