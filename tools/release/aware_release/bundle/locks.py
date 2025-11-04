"""Dependency lockfile helpers."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(slots=True)
class LockRequest:
    """Inputs required to build a dependency lockfile."""

    requirements: Iterable[str]
    platform: str
    output_path: Path
    python_version: Optional[str] = None


def generate_lock(request: LockRequest) -> Path:
    """Generate a lockfile for the requested platform."""

    output_path = request.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    resolved = _resolve_with_uv(request.requirements, request.python_version, request.platform)

    header = textwrap.dedent(
        f"""\
        # aware-release lockfile
        # platform: {request.platform}
        """
    ).strip()
    python_line = f"# python: {request.python_version}" if request.python_version else ""

    lines = [line for line in (header, python_line, "# generated via `uv pip compile --quiet`") if line]
    lines.extend(resolved)
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _resolve_with_uv(requirements: Iterable[str], python_version: Optional[str], platform: str) -> list[str]:
    requirements_list = [req for req in requirements if req.strip()]
    if not requirements_list:
        return []

    uv_executable = shutil.which("uv")
    platform_arg = _map_platform(platform)
    if uv_executable is None or platform_arg is None:
        return sorted(set(requirements_list))

    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False, suffix=".in") as req_file:
        req_file.write("\n".join(requirements_list))
        req_file.flush()
        req_path = Path(req_file.name)

    output_file = req_path.parent / "requirements.txt"

    cmd = [
        uv_executable,
        "pip",
        "compile",
        "--quiet",
        "--upgrade",
        "--no-build",
        "--no-header",
        "--no-annotate",
        "--output-file",
        str(output_file),
        "--python-platform",
        platform_arg,
    ]
    if python_version:
        cmd.extend(["--python-version", python_version])
    cmd.append(str(req_path))

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    req_path.unlink(missing_ok=True)
    if proc.returncode != 0 or not output_file.exists():
        output_file.unlink(missing_ok=True)
        return sorted(set(requirements_list))

    resolved = [
        line.strip()
        for line in output_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    output_file.unlink(missing_ok=True)
    return resolved or sorted(set(requirements_list))


def _map_platform(platform: str) -> Optional[str]:
    normalized = platform.replace("_", "-").lower()
    mapping = {
        "linux": "linux",
        "linux-x86-64": "x86_64-unknown-linux-gnu",
        "linux-x86_64": "x86_64-unknown-linux-gnu",
        "linux-aarch64": "aarch64-unknown-linux-gnu",
        "linux-arm64": "aarch64-unknown-linux-gnu",
        "macos": "macos",
        "macos-x86-64": "x86_64-apple-darwin",
        "macos-x86_64": "x86_64-apple-darwin",
        "macos-aarch64": "aarch64-apple-darwin",
        "macos-arm64": "aarch64-apple-darwin",
        "windows": "windows",
        "windows-x86-64": "x86_64-pc-windows-msvc",
        "windows-x86_64": "x86_64-pc-windows-msvc",
        "windows-aarch64": "aarch64-pc-windows-msvc",
        "windows-arm64": "aarch64-pc-windows-msvc",
    }
    return mapping.get(normalized)
