from __future__ import annotations

from pathlib import Path

from aware_release.bundle.locks import LockRequest, generate_lock


def _requirements_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "reqs.txt"
    path.write_text("requests==2.32.3\n", encoding="utf-8")
    return path


def test_generate_lock_creates_file(tmp_path: Path) -> None:
    output = tmp_path / "locks" / "linux.txt"
    reqs_path = _requirements_fixture(tmp_path)
    request = LockRequest(
        requirements=reqs_path.read_text(encoding="utf-8").splitlines(),
        platform="linux-x86_64",
        output_path=output,
        python_version="3.12",
    )

    path = generate_lock(request)
    assert path == output
    content = output.read_text(encoding="utf-8")
    assert "requests==2.32.3" in content
    assert "platform: linux-x86_64" in content
