from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for Py<3.11
    import tomli as tomllib  # type: ignore[no-redef]


_VERSION_RE = re.compile(r'^version\s*=\s*"(.*)"\s*$', re.MULTILINE)
_MODULE_VERSION_RE = re.compile(r'^(__version__\s*=\s*)"(.+)"\s*$', re.MULTILINE)
_CHANGELOG_HEADER_RE = re.compile(r"^##\s+([^\s]+)\s+-\s+(.+)$", re.MULTILINE)


@dataclass
class VersionConfig:
    project_root: Path
    pyproject_path: Path
    module_path: Path
    changelog_path: Path

    @classmethod
    def from_project(
        cls,
        project_root: Path,
        module_relpath: str,
        changelog: str = "CHANGELOG.md",
        pyproject: str = "pyproject.toml",
    ) -> "VersionConfig":
        root = project_root.resolve()
        return cls(
            project_root=root,
            pyproject_path=(root / pyproject).resolve(),
            module_path=(root / module_relpath).resolve(),
            changelog_path=(root / changelog).resolve(),
        )


def read_version(config: VersionConfig) -> str:
    data = tomllib.loads(config.pyproject_path.read_text(encoding="utf-8"))
    try:
        version = data["project"]["version"]
    except KeyError as exc:  # pragma: no cover - configuration error
        raise KeyError(f"Missing [project].version in {config.pyproject_path}") from exc
    return str(version)


def bump_version(version: str, bump: str = "patch") -> str:
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Version '{version}' is not in major.minor.patch format.")
    major, minor, patch = map(int, parts)
    bump_lower = bump.lower()
    if bump_lower == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_lower == "minor":
        minor += 1
        patch = 0
    elif bump_lower == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown bump type '{bump}'. Expected patch|minor|major.")
    return f"{major}.{minor}.{patch}"


def write_version(config: VersionConfig, new_version: str) -> None:
    _write_pyproject_version(config.pyproject_path, new_version)
    _write_module_version(config.module_path, new_version)


def update_changelog(
    config: VersionConfig,
    new_version: str,
    timestamp: _dt.datetime,
    summary_lines: Optional[Iterable[str]] = None,
) -> str:
    existing_text = config.changelog_path.read_text(encoding="utf-8") if config.changelog_path.exists() else ""
    summary = list(summary_lines or [])

    timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    header = f"## [{new_version}] - {timestamp_str}"

    if _has_changelog_entry(existing_text, new_version):
        return header  # entry already present; return header for idempotency

    marker = "## [Unreleased]"
    marker_idx = existing_text.find(marker)
    insert_idx = len(existing_text.rstrip())
    if marker_idx != -1:
        prefix = existing_text[:marker_idx]
        marker_end = marker_idx + len(marker)
        next_heading = existing_text.find("\n##", marker_end)
        if next_heading == -1:
            next_heading = len(existing_text)
        unreleased_body = existing_text[marker_end:next_heading]
        extracted, remainder = _split_unreleased_section(unreleased_body)
        if extracted:
            summary = _combine_summary_lines(summary, extracted)
        cleaned = remainder.strip("\n")
        suffix = existing_text[next_heading:]
        if cleaned:
            rebuilt_unreleased = f"{marker}\n{cleaned}\n"
            existing_text = prefix + rebuilt_unreleased + suffix
            insert_idx = len(prefix + rebuilt_unreleased)
        else:
            existing_text = prefix + suffix
            insert_idx = len(prefix)
    else:
        heading_match = _CHANGELOG_HEADER_RE.search(existing_text)
        if heading_match:
            insert_idx = heading_match.start()
        else:
            insert_idx = len(existing_text.rstrip())

    before = existing_text[:insert_idx].rstrip("\n")
    after = existing_text[insert_idx:].lstrip("\n")

    if not summary:
        summary = ["Automated release."]

    bullets = "\n".join(f"- {line}" for line in summary)
    entry_block = f"{header}\n{bullets}"

    pieces: List[str] = []
    if before.strip():
        pieces.append(before.strip())
    pieces.append(entry_block)
    if after.strip():
        pieces.append(after.strip())

    new_content = "\n\n".join(pieces).strip() + "\n"
    config.changelog_path.write_text(new_content, encoding="utf-8")
    return entry_block + "\n"


def validate_changelog_format(path: Path) -> List[str]:
    if not path.exists():
        return ["Changelog file does not exist."]
    content = path.read_text(encoding="utf-8")
    warnings: List[str] = []
    for match in _CHANGELOG_HEADER_RE.finditer(content):
        ts = match.group(2)
        try:
            _dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            warnings.append(f"Changelog entry for version {match.group(1)} has invalid timestamp '{ts}'.")
    return warnings


def _write_pyproject_version(pyproject_path: Path, new_version: str) -> None:
    content = pyproject_path.read_text(encoding="utf-8")
    if not _VERSION_RE.search(content):
        raise ValueError(f"Unable to locate version field in {pyproject_path}")
    updated = _VERSION_RE.sub(f'version = "{new_version}"', content, count=1)
    pyproject_path.write_text(updated, encoding="utf-8")


def _write_module_version(module_path: Path, new_version: str) -> None:
    content = module_path.read_text(encoding="utf-8")
    if not _MODULE_VERSION_RE.search(content):
        raise ValueError(f"Unable to locate __version__ assignment in {module_path}")
    updated = _MODULE_VERSION_RE.sub(rf'\1"{new_version}"', content, count=1)
    module_path.write_text(updated, encoding="utf-8")


def _normalize_version_label(label: str) -> str:
    return label.strip().strip("[]")


def _has_changelog_entry(content: str, version: str) -> bool:
    target = _normalize_version_label(version)
    for match in _CHANGELOG_HEADER_RE.finditer(content):
        if _normalize_version_label(match.group(1)) == target:
            return True
    return False


def _split_unreleased_section(section: str) -> tuple[list[str], str]:
    bullet_items: list[str] = []
    remaining_lines: list[str] = []
    for raw_line in section.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- "):
            bullet_items.append(stripped[2:].strip())
        elif stripped:
            remaining_lines.append(raw_line.rstrip())
    cleaned = "\n".join(remaining_lines).rstrip()
    return bullet_items, cleaned


_MARKDOWN_STRIP_RE = re.compile(r"[`*_]")


def _normalize_summary_line(line: str) -> str:
    cleaned = _MARKDOWN_STRIP_RE.sub("", line.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" .").lower()


def _combine_summary_lines(custom: Iterable[str], extracted: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    extracted_list = list(extracted)
    extracted_map: dict[str, str] = {}
    for line in extracted_list:
        key = _normalize_summary_line(line)
        if key not in extracted_map:
            extracted_map[key] = line

    for line in custom:
        key = _normalize_summary_line(line)
        if key in extracted_map:
            extracted_map.pop(key)
        candidate = line
        if key not in seen:
            result.append(candidate)
            seen.add(key)

    for line in extracted_list:
        key = _normalize_summary_line(line)
        if key not in seen:
            result.append(line)
            seen.add(key)

    return result
