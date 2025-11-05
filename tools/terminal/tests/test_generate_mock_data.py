import json
import subprocess
import sys
from pathlib import Path


def test_generate_mock_data(tmp_path: Path) -> None:
    module = "aware_terminal.mock_data.generate"
    output_dir = tmp_path / "fixtures"
    subprocess.check_call(
        [sys.executable, "-m", module, "--output", str(output_dir)],
        cwd=Path(__file__).resolve().parents[1],
    )

    environments = json.loads((output_dir / "environments.json").read_text())
    assert environments and environments[0]["slug"] == "aware-dev"

    events_dir = output_dir / "events"
    assert events_dir.exists()
    event_files = list(events_dir.glob("*.json"))
    assert event_files, "Expected generated event files"
