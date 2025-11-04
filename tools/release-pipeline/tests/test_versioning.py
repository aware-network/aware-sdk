from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from aware_release_pipeline.versioning import (
    VersionConfig,
    bump_version,
    read_version,
    update_changelog,
    validate_changelog_format,
    write_version,
)


@pytest.fixture()
def project_tmp(tmp_path: Path) -> VersionConfig:
    project = tmp_path / "pkg"
    (project / "aware_pkg").mkdir(parents=True)
    pyproject = project / "pyproject.toml"
    module = project / "aware_pkg" / "__init__.py"
    changelog = project / "CHANGELOG.md"

    pyproject.write_text(
        """
[project]
name = "aware-pkg"
version = "1.2.3"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    module.write_text('__version__ = "1.2.3"\n', encoding="utf-8")
    changelog.write_text("# Changelog\n\n", encoding="utf-8")

    return VersionConfig(
        project_root=project,
        pyproject_path=pyproject,
        module_path=module,
        changelog_path=changelog,
    )


def test_bump_version(project_tmp: VersionConfig) -> None:
    assert read_version(project_tmp) == "1.2.3"
    assert bump_version("1.2.3", "patch") == "1.2.4"
    assert bump_version("1.2.3", "minor") == "1.3.0"
    assert bump_version("1.2.3", "major") == "2.0.0"


def test_write_version_updates_pyproject_and_module(project_tmp: VersionConfig) -> None:
    write_version(project_tmp, "1.2.4")
    assert read_version(project_tmp) == "1.2.4"
    assert '__version__ = "1.2.4"' in project_tmp.module_path.read_text(encoding="utf-8")


def test_update_changelog_inserts_entry(project_tmp: VersionConfig) -> None:
    timestamp = dt.datetime(2025, 10, 26, 3, 15, 0, tzinfo=dt.timezone.utc)
    entry = update_changelog(project_tmp, "1.2.4", timestamp, ["Bumped patch version."])
    expected_header = "## [1.2.4] - 2025-10-26T03:15:00Z"
    assert expected_header in entry
    content = project_tmp.changelog_path.read_text(encoding="utf-8")
    assert expected_header in content
    warnings = validate_changelog_format(project_tmp.changelog_path)
    assert warnings == []


def test_update_changelog_inserts_before_existing_entries(project_tmp: VersionConfig) -> None:
    project_tmp.changelog_path.write_text(
        "# Changelog\n\n"
        "## [1.2.3] - 2025-10-20T00:00:00Z\n"
        "- Existing release.\n",
        encoding="utf-8",
    )
    timestamp = dt.datetime(2025, 10, 26, 3, 15, 0, tzinfo=dt.timezone.utc)
    update_changelog(project_tmp, "1.2.4", timestamp, ["Fresh release note."])
    content = project_tmp.changelog_path.read_text(encoding="utf-8")
    assert content.index("## [1.2.4]") < content.index("## [1.2.3]")
    assert "Fresh release note." in content


def test_update_changelog_no_duplicate_entries(project_tmp: VersionConfig) -> None:
    timestamp = dt.datetime(2025, 10, 26, 3, 15, 0, tzinfo=dt.timezone.utc)
    update_changelog(project_tmp, "1.2.4", timestamp, None)
    update_changelog(project_tmp, "1.2.4", timestamp, ["Ignored duplicate."])
    content = project_tmp.changelog_path.read_text(encoding="utf-8")
    assert content.count("## [1.2.4] -") == 1


def test_update_changelog_respects_unreleased_section(project_tmp: VersionConfig) -> None:
    project_tmp.changelog_path.write_text(
        "# Changelog\n\n"
        "## [Unreleased]\n"
        "- Pending note.\n\n"
        "## [1.2.3] - 2025-10-20T00:00:00Z\n"
        "- Existing release.\n",
        encoding="utf-8",
    )
    timestamp = dt.datetime(2025, 10, 26, 3, 15, 0, tzinfo=dt.timezone.utc)
    update_changelog(project_tmp, "1.2.4", timestamp, ["Bumped patch version."])
    content = project_tmp.changelog_path.read_text(encoding="utf-8")
    assert "## [Unreleased]" not in content
    released_section = "## [1.2.4] - 2025-10-26T03:15:00Z\n- Bumped patch version.\n- Pending note.\n"
    assert released_section in content
    assert content.index("## [1.2.4]") < content.index("## [1.2.3]")


def test_update_changelog_deduplicates_summary(project_tmp: VersionConfig) -> None:
    project_tmp.changelog_path.write_text(
        "# Changelog\n\n"
        "## [Unreleased]\n"
        "- Added resolver metadata to the shared secret registry (source, path, parse warnings) and exposed `resolve_secret_info()` for diagnostics.\n"
        "- Improved workflow error reporting to enumerate attempted resolvers and guide maintainers to `aware-cli release secrets-list`.\n",
        encoding="utf-8",
    )
    timestamp = dt.datetime(2025, 10, 26, 3, 15, 0, tzinfo=dt.timezone.utc)
    summary = [
        "Added resolver metadata to the shared secret registry (source, path, parse warnings) and exposed resolve_secret_info() for diagnostics.",
        "Improved workflow error reporting to enumerate attempted resolvers and guide maintainers to aware-cli release secrets-list.",
        "PyPI publish prep",
    ]
    update_changelog(project_tmp, "1.2.4", timestamp, summary)
    content = project_tmp.changelog_path.read_text(encoding="utf-8")
    assert "## [Unreleased]" not in content
    section = (
        "## [1.2.4] - 2025-10-26T03:15:00Z\n"
        "- Added resolver metadata to the shared secret registry (source, path, parse warnings) and exposed resolve_secret_info() for diagnostics.\n"
        "- Improved workflow error reporting to enumerate attempted resolvers and guide maintainers to aware-cli release secrets-list.\n"
        "- PyPI publish prep\n"
    )
    assert section in content
    assert content.count("resolve_secret_info()") == 1
