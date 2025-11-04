"""Provider packaging utilities."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(slots=True)
class ProviderArtifact:
    """Metadata describing a bundled provider."""

    slug: str
    version: str
    source: Path
    metadata: Mapping[str, object]


def discover_providers(paths: Iterable[Path]) -> list[ProviderArtifact]:
    """Scan candidate paths for provider packages."""

    artifacts: list[ProviderArtifact] = []
    for path in paths:
        path_obj = Path(path)
        if path_obj.is_file() and path_obj.suffix == ".whl":
            artifacts.append(_build_artifact_from_wheel(path_obj))
        elif path_obj.is_dir():
            for candidate in sorted(path_obj.glob("*.whl")):
                artifacts.append(_build_artifact_from_wheel(candidate))
    return artifacts


_WHEEL_PATTERN = re.compile(r"^(?P<name>[^-]+)-(?P<version>[\w\.]+)")


def _parse_wheel_name(filename: str) -> tuple[str, str]:
    match = _WHEEL_PATTERN.match(filename)
    if not match:
        raise ValueError(f"Unable to parse provider wheel name: {filename}")
    return match.group("name"), match.group("version")


def _build_artifact_from_wheel(path: Path) -> ProviderArtifact:
    slug, version = _parse_wheel_name(path.name)
    metadata: dict[str, object] = {}
    try:
        wheel_meta = _read_wheel_metadata(path)
        if wheel_meta.get("summary"):
            metadata["summary"] = wheel_meta["summary"]
        requires = wheel_meta.get("requires", [])
        if requires:
            metadata["requires"] = requires
    except Exception:
        # best-effort metadata extraction
        pass
    return ProviderArtifact(
        slug=slug,
        version=version,
        source=path,
        metadata=metadata,
    )


def _read_wheel_metadata(path: Path) -> dict[str, object]:
    parser = Parser()
    metadata_text = None
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.endswith(".dist-info/METADATA"):
                with archive.open(name) as handle:
                    metadata_text = handle.read().decode("utf-8", errors="replace")
                break

    if metadata_text is None:
        return {}

    message = parser.parsestr(metadata_text)
    requires = [value.strip() for value in message.get_all("Requires-Dist", [])]
    summary = message.get("Summary", "").strip()

    payload: dict[str, object] = {}
    if summary:
        payload["summary"] = summary
    if requires:
        payload["requires"] = requires
    return payload
