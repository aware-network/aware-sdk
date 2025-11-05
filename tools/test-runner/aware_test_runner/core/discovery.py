"""Test suite discovery functionality driven by manifest configuration."""

from __future__ import annotations

import shlex
from collections import deque
from functools import lru_cache
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

from ..config import DiscoveryRule, ManifestData
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


@lru_cache(maxsize=128)
def _load_pyproject_data(directory: str) -> Dict[str, Any]:
    """Read and cache pyproject metadata for discovery purposes."""
    dir_path = Path(directory)
    pyproject = dir_path / "pyproject.toml"
    if tomllib is None or not pyproject.is_file():
        return {}
    with pyproject.open("rb") as handle:
        return tomllib.load(handle)


def _slugify(value: str, *, allow_dash: bool = False) -> str:
    """Convert a string to a slug suitable for suite identifiers."""
    if not value:
        return ""
    chars: List[str] = []
    for char in value:
        if char.isalnum() or (allow_dash and char == "-"):
            chars.append(char)
        else:
            chars.append("_")
    slug = "".join(chars).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or value.strip()


def _title_case(value: str) -> str:
    if not value:
        return ""
    cleaned = value.replace("_", " ").replace("-", " ")
    return " ".join(part for part in cleaned.split() if part).title()


class _FormatDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


class TestSuiteDiscovery:
    """Auto-discovery of test suites orchestrated by manifest-defined rules."""

    def __init__(self, aware_root: str, manifest: ManifestData):
        self.aware_root = Path(aware_root)
        self._manifest = manifest
        self._runtime_entries = manifest.runtime_entries
        self._stable_entries = manifest.stable_entries
        self._stable_names = self._extract_stable_names(self._stable_entries)
        self._stable_partials = self._extract_stable_partials(self._stable_entries)
        self._discovery_rules = [rule for rule in manifest.discovery_rules if rule.enabled]
        self._category_alias_map = self._build_category_alias_map()
        self._category_presets = self._build_category_presets()
        self._suite_cache: Optional[Dict[str, TestSuite]] = None

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
        return sorted(self.category_presets().keys())

    def discover_all_suites(self) -> Dict[str, TestSuite]:
        """Discover all test suites across discovery rules and runtime manifest entries."""
        return dict(self._all_suites())

    def discover_all_runtime_entries(self) -> List[Dict]:
        """Expose runtime entries for downstream tooling."""
        return list(self._runtime_entries)

    def discover_manifest_suites(self) -> Dict[str, TestSuite]:
        """Load suites defined via runtime manifests."""
        suites: Dict[str, TestSuite] = {}
        for entry in self._runtime_entries:
            suite = self._build_manifest_suite(entry)
            if suite is not None:
                suites[suite.name] = suite
        return suites

    def get_suites_by_category(self, category: str) -> Dict[str, TestSuite]:
        """Get all suites for a specific category."""
        if category == "stable":
            if not self._stable_names:
                return {}
            available = self._all_suites()
            partials = self._stable_partials
            suites: Dict[str, TestSuite] = {}
            missing = []
            for name in self._stable_names:
                suite = available.get(name)
                if suite is None:
                    missing.append(name)
                    continue
                selectors = partials.get(name)
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

        target = self._category_alias_map.get(category, category)
        suites = {
            name: suite
            for name, suite in self._all_suites().items()
            if suite.category == target
        }
        return suites

    def _all_suites(self) -> Dict[str, TestSuite]:
        if self._suite_cache is None:
            suites: Dict[str, TestSuite] = {}
            for rule in self._discovery_rules:
                suites.update(self._discover_with_rule(rule))
            suites.update(self.discover_manifest_suites())
            self._suite_cache = suites
        return self._suite_cache

    def _discover_with_rule(self, rule: DiscoveryRule) -> Dict[str, TestSuite]:
        if rule.type != "package":
            print(f"Warning: Unsupported discovery rule type '{rule.type}' for rule '{rule.id}'")
            return {}
        return self._discover_package_rule(rule)

    def _discover_package_rule(self, rule: DiscoveryRule) -> Dict[str, TestSuite]:
        root_dir = (self.aware_root / rule.root).resolve()
        if not root_dir.exists():
            return {}

        suites: Dict[str, TestSuite] = {}
        queue: deque[tuple[Path, Path]] = deque()
        queue.append((root_dir, Path()))
        tests_dir_parts = Path(rule.tests_dir).parts or ("tests",)
        first_tests_segment = tests_dir_parts[0]

        while queue:
            current_dir, relative = queue.popleft()
            depth = len(relative.parts)
            is_root = depth == 0

            if (not is_root) or rule.include_root:
                if self._matches_patterns(relative, rule.include, rule.exclude):
                    suite = self._build_suite_from_rule(rule, current_dir, relative)
                    if suite is not None and suite.name not in suites:
                        suites[suite.name] = suite

            if rule.max_depth is not None and depth >= rule.max_depth:
                continue

            try:
                children = sorted(current_dir.iterdir(), key=lambda p: p.name)
            except OSError:
                continue

            for child in children:
                if not child.is_dir():
                    continue
                if self._should_skip_directory(child.name):
                    continue
                if child.name == first_tests_segment:
                    continue
                queue.append((child, relative / child.name))

        return suites

    def _build_suite_from_rule(self, rule: DiscoveryRule, directory: Path, relative: Path) -> Optional[TestSuite]:
        tests_dir = directory.joinpath(*Path(rule.tests_dir).parts or ("tests",))
        if not tests_dir.exists() or not tests_dir.is_dir():
            return None

        metadata_value = self._extract_metadata(directory, rule.metadata_field)
        if rule.require_metadata and not metadata_value:
            return None

        suite_name = self._build_suite_name(rule, relative, metadata_value)
        if not suite_name:
            return None

        description = self._build_suite_description(rule, relative, metadata_value, suite_name)

        return TestSuite(
            name=suite_name,
            path=str(tests_dir),
            category=rule.category,
            description=description,
        )

    def _matches_patterns(self, relative: Path, include: List[str], exclude: List[str]) -> bool:
        relative_str = str(relative).replace("\\", "/")
        name = relative.name if relative_str else ""

        if include:
            if not any(
                fnmatch(relative_str, pattern) or (name and fnmatch(name, pattern))
                for pattern in include
            ):
                return False

        if exclude:
            if any(
                fnmatch(relative_str, pattern) or (name and fnmatch(name, pattern))
                for pattern in exclude
            ):
                return False

        return True

    @staticmethod
    def _should_skip_directory(name: str) -> bool:
        return name in {"__pycache__"} or name.startswith(".") or name.startswith("_")

    def _extract_metadata(self, directory: Path, metadata_field: Optional[str]) -> Optional[str]:
        if not metadata_field:
            return None
        data = _load_pyproject_data(str(directory))
        value: Any = data
        for part in metadata_field.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        if isinstance(value, str):
            return value
        return None

    def _build_suite_name(self, rule: DiscoveryRule, relative: Path, metadata_value: Optional[str]) -> Optional[str]:
        cfg = rule.name
        context = self._build_context(rule, relative, metadata_value)

        if cfg.strategy == "path_join":
            parts = list(relative.parts)
            if cfg.reverse:
                parts = list(reversed(parts))
            slug_parts = [_slugify(part) for part in parts if part]
            if not slug_parts and cfg.fallback:
                fallback = self._fallback_name(cfg.fallback, context, rule, metadata_value)
                return fallback
            if not slug_parts:
                slug_parts = [_slugify(metadata_value or rule.id)]
            return cfg.delimiter.join(slug_parts)

        if cfg.strategy == "metadata":
            if metadata_value:
                return _slugify(metadata_value)
            return self._fallback_name(cfg.fallback, context, rule, metadata_value)

        if cfg.strategy == "template":
            template = cfg.template or "{path_slug}"
            formatted = self._safe_format(template, context)
            if formatted:
                return formatted
            return self._fallback_name(cfg.fallback, context, rule, metadata_value)

        return None

    def _fallback_name(
        self,
        fallback: Optional[str],
        context: Dict[str, Any],
        rule: DiscoveryRule,
        metadata_value: Optional[str],
    ) -> Optional[str]:
        if not fallback:
            return None
        if fallback == "metadata" and metadata_value:
            return _slugify(metadata_value)
        if fallback == "path" and context.get("path_slug"):
            return context["path_slug"]
        if fallback == "name" and context.get("name_slug"):
            return context["name_slug"]
        if fallback == "rule":
            return _slugify(rule.id)
        return None

    def _build_suite_description(
        self,
        rule: DiscoveryRule,
        relative: Path,
        metadata_value: Optional[str],
        suite_name: str,
    ) -> str:
        context = self._build_context(rule, relative, metadata_value)
        context["suite_name"] = suite_name
        if rule.description:
            return self._safe_format(rule.description, context) or rule.description
        display = context.get("display_title") or context.get("name_title") or rule.category.title()
        return f"{display} {rule.category} tests"

    def _build_context(
        self,
        rule: DiscoveryRule,
        relative: Path,
        metadata_value: Optional[str],
    ) -> Dict[str, Any]:
        parts = list(relative.parts)
        name = parts[-1] if parts else rule.root.strip("/").split("/")[-1]

        path_slug = "_".join(_slugify(part) for part in parts if part)
        display = metadata_value or name or rule.id

        context: Dict[str, Any] = {
            "rule_id": rule.id,
            "category": rule.category,
            "path": "/".join(parts),
            "path_parts": parts,
            "path_slug": path_slug,
            "path_dash": "-".join(_slugify(part, allow_dash=True) for part in parts if part),
            "path_title": " ".join(_title_case(part) for part in parts if part),
            "name": name,
            "name_slug": _slugify(name),
            "name_dash": name.replace("_", "-"),
            "name_title": _title_case(name),
            "language": parts[0] if parts else "",
            "language_title": _title_case(parts[0]) if parts else "",
            "metadata_value": metadata_value or "",
            "metadata_slug": _slugify(metadata_value or ""),
            "metadata_title": _title_case(metadata_value or ""),
            "display": display,
            "display_slug": _slugify(display),
            "display_title": _title_case(display),
        }
        return context

    @staticmethod
    def _safe_format(template: str, context: Dict[str, Any]) -> str:
        try:
            return template.format_map(_FormatDict(context))
        except Exception:  # pragma: no cover - defensive
            return template

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

    def _build_category_alias_map(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for category in list(BASE_CATEGORY_PRESETS.keys()) + ["stable"]:
            mapping.setdefault(category, category)

        for rule in self._discovery_rules:
            mapping.setdefault(rule.category, rule.category)
            for alias in rule.category_aliases:
                mapping[alias] = rule.category

        for entry in self._runtime_entries:
            category = entry.get("category") or entry.get("runtime") or "external"
            if isinstance(category, str):
                mapping.setdefault(category, category)

        return mapping

    def _build_category_presets(self) -> Dict[str, List[str]]:
        presets = {name: entries[:] for name, entries in BASE_CATEGORY_PRESETS.items()}

        for category in self._category_alias_map:
            presets.setdefault(category, [])

        for entry in self._runtime_entries:
            category = entry.get("category") or entry.get("runtime") or "external"
            name = entry.get("name")
            if isinstance(category, str) and isinstance(name, str):
                presets.setdefault(category, [])
                if name not in presets[category]:
                    presets[category].append(name)

        presets["stable"] = self._stable_names
        return presets

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
