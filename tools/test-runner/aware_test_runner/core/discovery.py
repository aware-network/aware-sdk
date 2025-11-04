"""Test suite discovery functionality with manifest-driven configuration."""

from __future__ import annotations

import shlex
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional

from ..config import ManifestData
from .models import TestSuite

BASE_CATEGORY_PRESETS: Dict[str, List[str]] = {
    "grammar": [
        "aware-grammar",
        "sql-grammar",
        "python-grammar",
        "dart-grammar",
    ],
    "lib": [
        "core",
        "evolution",
        "utils",
    ],
    "domains": [
        "meta",
        "primitive",
        "structure",
    ],
    "tools": [],
}


class TestSuiteDiscovery:
    """Auto-discovery of test suites organized by category."""

    def __init__(self, aware_root: str, manifest: ManifestData):
        self.aware_root = Path(aware_root)
        self._manifest = manifest
        self._runtime_entries = manifest.runtime_entries
        self._stable_entries = manifest.stable_entries
        self._stable_names = self._extract_stable_names(self._stable_entries)
        self._stable_partials = self._extract_stable_partials(self._stable_entries)
        self._category_presets = self._build_category_presets()

    def category_presets(self) -> Dict[str, List[str]]:
        """Return cached category selectors derived from manifests + discovery defaults."""
        return self._category_presets

    def default_selector_presets(self) -> List[str]:
        """Return default suite selectors used when no explicit selectors are provided."""
        presets: List[str] = []
        ordered_categories = ["grammar", "lib", "domains", "tools"]
        category_presets = self.category_presets()
        for category in ordered_categories:
            presets.extend(category_presets.get(category, []))
        for category, entries in category_presets.items():
            if category in ordered_categories + ["stable"]:
                continue
            presets.extend(entries)
        return presets

    def available_categories(self) -> List[str]:
        """Expose available categories for CLI consumption."""
        return list(self.category_presets().keys())

    def discover_grammar_suites(self) -> Dict[str, TestSuite]:
        """Discover grammar test suites from languages directory."""
        suites: Dict[str, TestSuite] = {}
        languages_dir = self.aware_root / "languages"

        if not languages_dir.exists():
            return suites

        for lang_dir in languages_dir.iterdir():
            if not lang_dir.is_dir() or lang_dir.name.startswith("_"):
                continue

            grammar_tests_dir = lang_dir / "grammar" / "grammar" / "tests"
            if grammar_tests_dir.exists() and grammar_tests_dir.is_dir():
                suite_name = f"{lang_dir.name}-grammar"
                description = f"{lang_dir.name.title()} grammar tests"

                suites[suite_name] = TestSuite(
                    name=suite_name,
                    path=str(grammar_tests_dir),
                    category="grammar",
                    description=description,
                )

        return suites

    def discover_lib_suites(self) -> Dict[str, TestSuite]:
        """Discover library test suites from lib directory."""
        suites: Dict[str, TestSuite] = {}
        libs_dir = self.aware_root / "libs"
        if not libs_dir.exists():
            return suites

        queue = deque([libs_dir])
        while queue:
            current_dir = queue.popleft()
            for child_dir in current_dir.iterdir():
                if not child_dir.is_dir():
                    continue
                if child_dir.name.startswith((".", "_")) or child_dir.name == "__pycache__":
                    continue
                if child_dir.name == "tests":
                    continue

                tests_dir = child_dir / "tests"
                if tests_dir.exists() and tests_dir.is_dir():
                    try:
                        relative_path = child_dir.relative_to(libs_dir)
                    except ValueError:
                        continue
                    if "tests" in relative_path.parts:
                        continue

                    if len(relative_path.parts) > 2:
                        continue

                    if not self._has_project_metadata(child_dir):
                        continue

                    suite_name = self._build_lib_suite_name(relative_path)
                    if suite_name in suites:
                        continue

                    description = self._build_lib_suite_description(relative_path)
                    suites[suite_name] = TestSuite(
                        name=suite_name,
                        path=str(tests_dir),
                        category="lib",
                        description=description,
                    )

                queue.append(child_dir)

        return suites

    def discover_domain_suites(self) -> Dict[str, TestSuite]:
        """Discover domain test suites from domains directory."""
        suites: Dict[str, TestSuite] = {}
        domains_dir = self.aware_root / "languages" / "python" / "domains"

        if not domains_dir.exists():
            return suites

        for domain_dir in domains_dir.iterdir():
            if not domain_dir.is_dir():
                continue

            tests_dir = domain_dir / "tests"
            if tests_dir.exists() and tests_dir.is_dir():
                suite_name = domain_dir.name
                description = f"{domain_dir.name.title()} domain tests"

                suites[suite_name] = TestSuite(
                    name=suite_name,
                    path=str(tests_dir),
                    category="domains",
                    description=description,
                )

        return suites

    def discover_tool_suites(self) -> Dict[str, TestSuite]:
        """Discover tooling test suites from tools directory."""
        suites: Dict[str, TestSuite] = {}
        tools_dir = self.aware_root / "tools"

        if not tools_dir.exists():
            return suites

        for tool_dir in tools_dir.iterdir():
            if not tool_dir.is_dir():
                continue

            tests_dir = tool_dir / "tests"
            if tests_dir.exists() and tests_dir.is_dir():
                suite_name = tool_dir.name.replace("_", "-")
                description = f"{tool_dir.name} tooling tests"
                suites[suite_name] = TestSuite(
                    name=suite_name,
                    path=str(tests_dir),
                    category="tools",
                    description=description,
                )

        return suites

    def discover_manifest_suites(self) -> Dict[str, TestSuite]:
        """Load suites defined via runtime manifests."""
        suites: Dict[str, TestSuite] = {}
        for entry in self._runtime_entries:
            suite = self._build_manifest_suite(entry)
            if suite is not None:
                suites[suite.name] = suite
        return suites

    def discover_all_suites(self) -> Dict[str, TestSuite]:
        """Discover all test suites across all categories."""
        all_suites: Dict[str, TestSuite] = {}

        all_suites.update(self.discover_grammar_suites())
        all_suites.update(self.discover_lib_suites())
        all_suites.update(self.discover_domain_suites())
        all_suites.update(self.discover_tool_suites())
        all_suites.update(self.discover_manifest_suites())

        return all_suites

    def get_suites_by_category(self, category: str) -> Dict[str, TestSuite]:
        """Get all suites for a specific category."""
        suites: Dict[str, TestSuite] = {}
        if category == "grammar":
            return self.discover_grammar_suites()
        if category in {"lib", "libs"}:
            return self.discover_lib_suites()
        if category == "domains":
            return self.discover_domain_suites()
        if category == "tools":
            return self.discover_tool_suites()
        if category == "stable":
            if not self._stable_names:
                return {}
            available = self.discover_all_suites()
            missing = []
            for name in self._stable_names:
                suite = available.get(name)
                if suite is None:
                    missing.append(name)
                    continue
                selectors = self._stable_partials.get(name)
                if selectors:
                    suites[name] = TestSuite(
                        name=suite.name,
                        path=suite.path,
                        category=suite.category,
                        description=suite.description,
                        runtime=suite.runtime,
                        command=suite.command,
                        env=suite.env,
                        test_selectors=selectors,
                        tags=suite.tags,
                    )
                else:
                    suites[name] = suite
            if missing:
                print(f"Warning: Stable suite(s) not found: {', '.join(missing)}")
            return suites

        manifest_categories = self._manifest_suites_by_category()
        if category in manifest_categories:
            return manifest_categories[category]
        return suites

    def _manifest_suites_by_category(self) -> Dict[str, Dict[str, TestSuite]]:
        grouped: Dict[str, Dict[str, TestSuite]] = {}
        for suite in self.discover_manifest_suites().values():
            grouped.setdefault(suite.category, {})[suite.name] = suite
        return grouped

    def _build_manifest_suite(self, entry: Dict) -> Optional[TestSuite]:
        name = entry.get("name")
        path_value = entry.get("path")
        if not isinstance(name, str) or not isinstance(path_value, str):
            return None

        suite_path = self.aware_root / path_value
        runtime = entry.get("runtime", "python")
        category = entry.get("category") or runtime or "external"
        description = entry.get("description", "")

        command_entry = entry.get("command")
        if isinstance(command_entry, str):
            command = shlex.split(command_entry)
        elif isinstance(command_entry, list):
            command = [str(item) for item in command_entry]
        else:
            command = None

        env_entry = entry.get("env")
        if isinstance(env_entry, dict):
            env = {str(k): str(v) for k, v in env_entry.items()}
        else:
            env = None

        selectors_entry = entry.get("tests")
        if isinstance(selectors_entry, list):
            selectors = [s for s in selectors_entry if isinstance(s, str)]
        else:
            selectors = None

        tags_entry = entry.get("tags")
        if isinstance(tags_entry, list):
            tags = [t for t in tags_entry if isinstance(t, str)]
        else:
            tags = []

        setup_entry = entry.get("setup")
        setup_commands: List[List[str]] = []
        if isinstance(setup_entry, list):
            if all(isinstance(part, str) for part in setup_entry):
                setup_commands.append([str(part) for part in setup_entry])
            else:
                for cmd in setup_entry:
                    if isinstance(cmd, list) and cmd:
                        setup_commands.append([str(part) for part in cmd])
        elif isinstance(setup_entry, str):
            setup_commands.append(shlex.split(setup_entry))

        return TestSuite(
            name=name,
            path=str(suite_path),
            category=category,
            description=description,
            runtime=runtime,
            command=command,
            env=env,
            test_selectors=selectors,
            tags=tags,
            setup_commands=setup_commands,
        )

    @staticmethod
    def _extract_stable_names(entries: List[object]) -> List[str]:
        names: List[str] = []
        for entry in entries:
            if isinstance(entry, str):
                names.append(entry)
            elif isinstance(entry, dict):
                name = entry.get("name")
                if isinstance(name, str):
                    names.append(name)
        return names

    @staticmethod
    def _extract_stable_partials(entries: List[object]) -> Dict[str, List[str]]:
        partials: Dict[str, List[str]] = {}
        for entry in entries:
            if isinstance(entry, dict):
                name = entry.get("name")
                tests = entry.get("tests")
                if isinstance(name, str) and isinstance(tests, list):
                    selectors = [s for s in tests if isinstance(s, str)]
                    if selectors:
                        partials[name] = selectors
        return partials

    def _build_category_presets(self) -> Dict[str, List[str]]:
        presets = {name: entries[:] for name, entries in BASE_CATEGORY_PRESETS.items()}
        if "lib" in presets and "libs" not in presets:
            presets["libs"] = presets["lib"][:]
        for entry in self._runtime_entries:
            category = entry.get("category") or entry.get("runtime") or "external"
            name = entry.get("name")
            if isinstance(name, str):
                presets.setdefault(category, [])
                if name not in presets[category]:
                    presets[category].append(name)
        presets["stable"] = self._stable_names
        return presets

    def discover_all_runtime_entries(self) -> List[Dict]:
        """Expose runtime entries for downstream tooling."""
        return list(self._runtime_entries)

    @staticmethod
    def _build_lib_suite_name(relative_path: Path) -> str:
        """Construct a deterministic suite name from the library path."""
        parts = [part for part in reversed(relative_path.parts) if part]
        if not parts:
            return "lib"
        return "_".join(parts)

    @staticmethod
    def _build_lib_suite_description(relative_path: Path) -> str:
        """Create a human friendly description for library suites."""
        words = []
        for part in relative_path.parts:
            if not part:
                continue
            words.append(part.replace("_", " ").title())
        label = " ".join(words) if words else "Library"
        return f"{label} library tests"

    @staticmethod
    def _has_project_metadata(candidate_dir: Path) -> bool:
        """Check if the directory looks like a standalone project."""
        for metadata_file in ("pyproject.toml", "setup.cfg", "setup.py"):
            if candidate_dir.joinpath(metadata_file).exists():
                return True
        return False


def expand_suite_selectors(selectors: List[str], discovery: TestSuiteDiscovery) -> List[str]:
    """Expand suite selectors to individual suite names."""
    if not selectors:
        return discovery.default_selector_presets()

    expanded = []
    available_suites = discovery.discover_all_suites()
    category_presets = discovery.category_presets()

    for selector in selectors:
        if selector == "all":
            expanded.extend(available_suites.keys())
        elif selector in category_presets:
            category_suites = discovery.get_suites_by_category(selector)
            expanded.extend(category_suites.keys())
        elif ":" in selector:
            category, suite_name = selector.split(":", 1)
            if category in category_presets:
                category_suites = discovery.get_suites_by_category(category)
                if suite_name in category_suites:
                    expanded.append(suite_name)
                else:
                    print(f"Warning: Unknown suite '{suite_name}' in category '{category}'")
            else:
                print(f"Warning: Unknown category '{category}'")
        elif selector in available_suites:
            expanded.append(selector)
        else:
            print(f"Warning: Unknown test selector '{selector}'")

    seen = set()
    result = []
    for suite in expanded:
        if suite not in seen:
            seen.add(suite)
            result.append(suite)

    return result
