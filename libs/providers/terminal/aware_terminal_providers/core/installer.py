"\"\"\"Common install/update helpers for terminal providers.\"\"\""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass(slots=True)
class InstallRequest:
    package: str
    binary_name: str
    version_args: Iterable[str] = ("--version",)


@dataclass(slots=True)
class InstallResult:
    success: bool
    message: str
    version: Optional[str] = None
    command: Optional[List[str]] = None
    binary_path: Optional[str] = None


def resolve_binary(binary_name: str) -> Optional[str]:
    return shutil.which(binary_name)


def detect_version(binary_path: str, version_args: Iterable[str]) -> Optional[str]:
    try:
        output = subprocess.check_output([binary_path, *version_args], stderr=subprocess.STDOUT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return output or None


def ensure_npm_global_install(request: InstallRequest, *, npm_executable: str = "npm") -> InstallResult:
    if shutil.which(npm_executable) is None:
        return InstallResult(
            success=False,
            message=f"npm executable '{npm_executable}' not found in PATH. Install Node.js/npm to manage {request.package}.",
            command=[npm_executable, "install", "-g", request.package],
        )

    command = [npm_executable, "install", "-g", request.package]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        return InstallResult(
            success=False,
            message=f"npm install failed with exit code {exc.returncode}",
            command=command,
        )

    binary_path = resolve_binary(request.binary_name)
    if not binary_path:
        return InstallResult(
            success=False,
            message=f"Installation completed but '{request.binary_name}' not found in PATH.",
            command=command,
        )

    version = detect_version(binary_path, request.version_args)
    return InstallResult(
        success=True,
        message=f"Installed {request.package} ({version or 'unknown version'}).",
        version=version,
        command=command,
        binary_path=binary_path,
    )


def evaluate_installation(request: InstallRequest) -> InstallResult:
    binary_path = resolve_binary(request.binary_name)
    if binary_path:
        version = detect_version(binary_path, request.version_args)
        return InstallResult(
            success=True,
            message=f"{request.binary_name} already installed ({version or 'unknown version'}).",
            version=version,
            binary_path=binary_path,
        )

    install_cmd = ["npm", "install", "-g", request.package]
    return InstallResult(
        success=False,
        message=f"{request.binary_name} not found. Install with `npm install -g {request.package}`.",
        command=install_cmd,
    )


def ensure_installed(
    request: InstallRequest,
    *,
    auto_install: bool = False,
    force: bool = False,
    npm_executable: str = "npm",
) -> InstallResult:
    binary_path = resolve_binary(request.binary_name)
    if binary_path and not force:
        version = detect_version(binary_path, request.version_args)
        return InstallResult(
            success=True,
            message=f"{request.binary_name} already installed ({version or 'unknown version'}).",
            version=version,
            binary_path=binary_path,
        )

    if not auto_install:
        install_cmd = [npm_executable, "install", "-g", request.package]
        return InstallResult(
            success=False,
            message=(
                f"{request.binary_name} not found. Enable auto-install or run `{' '.join(install_cmd)}` manually."
            ),
            command=install_cmd,
        )

    result = ensure_npm_global_install(request, npm_executable=npm_executable)
    if result.success and not result.binary_path:
        new_path = resolve_binary(request.binary_name)
        if new_path:
            result.binary_path = new_path
            result.version = detect_version(new_path, request.version_args)
    return result
