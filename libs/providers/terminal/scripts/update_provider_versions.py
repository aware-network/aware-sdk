#!/usr/bin/env python3
"""Fetch provider release versions and update local manifests."""

from __future__ import annotations

import argparse
import os
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import re

BASE_DIR = Path(__file__).resolve().parents[1]
PROVIDERS_DIR = BASE_DIR / "aware_terminal_providers" / "providers"


@dataclass
class ProviderConfig:
    slug: str
    package: str
    channels: Dict[str, str]  # channel -> npm tag
    release_source: Optional["ReleaseSource"] = None


@dataclass
class ReleaseSource:
    kind: str  # "github_release", "github_changelog", "manual"
    owner: Optional[str] = None
    repo: Optional[str] = None
    tag_prefix: str = ""
    tag_suffix: str = ""
    manual_dir: Optional[Path] = None
    changelog_path: Optional[str] = None
    changelog_anchor_template: Optional[str] = None


PROVIDERS: Dict[str, ProviderConfig] = {
    "codex": ProviderConfig(
        slug="codex",
        package="@openai/codex",
        channels={"latest": "latest"},
        release_source=ReleaseSource(
            kind="github_release",
            owner="openai",
            repo="codex",
            tag_prefix="rust-v",
        ),
    ),
    "claude-code": ProviderConfig(
        slug="claude-code",
        package="@anthropic-ai/claude-code",
        channels={"latest": "latest"},
        release_source=ReleaseSource(
            kind="github_changelog",
            owner="anthropics",
            repo="claude-code",
            changelog_path="CHANGELOG.md",
            changelog_anchor_template="https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md",
        ),
    ),
    "gemini": ProviderConfig(
        slug="gemini",
        package="@google/gemini-cli",
        channels={
            "latest": "latest",
            "preview": "preview",
            "nightly": "nightly",
        },
        release_source=ReleaseSource(
            kind="github_release",
            owner="google-gemini",
            repo="gemini-cli",
            tag_prefix="v",
        ),
    ),
}


def fetch_dist_tags(package: str) -> Dict[str, str]:
    url = f"https://registry.npmjs.org/{package}"
    try:
        with urlopen(url) as response:  # type: ignore[arg-type]
            data = json.load(response)
            return data.get("dist-tags", {})
    except (URLError, HTTPError) as exc:
        raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc


def _provider_dir(slug: str) -> Path:
    path = PROVIDERS_DIR / slug
    if path.exists():
        return path
    alt = slug.replace("-", "_")
    alt_path = PROVIDERS_DIR / alt
    return alt_path


def load_manifest(slug: str) -> Dict[str, object]:
    path = _provider_dir(slug) / "releases.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON in {path}") from exc
    return {"provider": slug, "channels": {}}


def save_manifest(slug: str, manifest: Dict[str, object]) -> None:
    directory = _provider_dir(slug)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "releases.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _github_release_notes(source: ReleaseSource, version: str) -> Optional[Dict[str, str]]:
    if source.owner is None or source.repo is None:
        return None

    tag = f"{source.tag_prefix}{version}{source.tag_suffix}"
    url = f"https://api.github.com/repos/{source.owner}/{source.repo}/releases/tags/{tag}"
    headers = {"Accept": "application/vnd.github+json"}
    token = (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN_PROVIDERS")
        or os.environ.get("AWARE_PROVIDER_RELEASE_TOKEN")
    )
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    try:
        with urlopen(request) as response:  # type: ignore[arg-type]
            payload = json.load(response)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Failed to fetch GitHub release {url}: {exc}") from exc

    body = payload.get("body", "") or ""
    summary = summarise_release_notes(body)
    html_url = payload.get("html_url") or payload.get("url")
    release_notes = {
        "summary": summary,
        "url": html_url,
        "source": "github_release",
    }
    return release_notes


def _github_changelog_notes(source: ReleaseSource, version: str) -> Optional[Dict[str, str]]:
    if source.owner is None or source.repo is None or source.changelog_path is None:
        return None

    base = f"https://raw.githubusercontent.com/{source.owner}/{source.repo}/main/{source.changelog_path}"
    headers = {}
    token = (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN_PROVIDERS")
        or os.environ.get("AWARE_PROVIDER_RELEASE_TOKEN")
    )
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(base, headers=headers)
    try:
        with urlopen(request) as response:  # type: ignore[arg-type]
            text = response.read().decode("utf-8")
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Failed to fetch changelog {base}: {exc}") from exc

    summary = summarise_changelog(text, version)
    anchor = source.changelog_anchor_template or base
    release_notes = {
        "summary": summary,
        "url": anchor,
        "source": "github_changelog",
    }
    return release_notes


def summarise_release_notes(body: str, limit: int = 200) -> str:
    lines = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            if lines:
                break
            continue
        if line.startswith("#"):
            continue
        cleaned = line.lstrip("*-• ")
        lines.append(cleaned)
        if len(lines) >= 3:
            break
    summary = "; ".join(lines) if lines else "Release notes available at the linked changelog."
    if len(summary) > limit:
        summary = summary[: limit - 1].rstrip() + "…"
    return summary


def update_provider(config: ProviderConfig, *, write: bool, verbose: bool) -> bool:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest = load_manifest(config.slug)
    channels = manifest.setdefault("channels", {})

    try:
        dist_tags = fetch_dist_tags(config.package)
    except RuntimeError as exc:
        print(f"[WARN] {exc}", file=sys.stderr)
        return False

    changed = False
    for channel, npm_tag in config.channels.items():
        version = dist_tags.get(npm_tag)
        if not version:
            print(
                f"[WARN] npm tag '{npm_tag}' not found for {config.package}",
                file=sys.stderr,
            )
            continue

        channel_entry = channels.setdefault(channel, {})
        previous = channel_entry.get("version")
        if previous != version:
            changed = True
            channel_entry["version"] = version
        channel_entry["npm_tag"] = npm_tag
        channel_entry["updated_at"] = now

        if config.release_source:
            notes = None
            try:
                if config.release_source.kind == "github_release":
                    notes = _github_release_notes(config.release_source, version)
                elif config.release_source.kind == "github_changelog":
                    notes = _github_changelog_notes(config.release_source, version)
            except RuntimeError as exc:
                print(f"[WARN] {exc}", file=sys.stderr)
            if notes:
                notes["fetched_at"] = now
                channel_entry["release_notes"] = notes

    if changed:
        if write:
            save_manifest(config.slug, manifest)
            if verbose:
                print(f"[WRITE] Updated {config.slug} manifest")
        else:
            print(f"[DRY-RUN] Would update {config.slug} manifest")
    else:
        if verbose:
            print(f"[OK] {config.slug} manifest already up to date")

    return changed and write


def summarise_changelog(text: str, version: str, limit: int = 200) -> str:
    pattern_variants = [
        rf"^##\s*v?{re.escape(version)}\b",
        rf"^#\s*v?{re.escape(version)}\b",
        rf"^v?{re.escape(version)}\b",
    ]
    lines = text.splitlines()
    match_index = None
    for idx, line in enumerate(lines):
        for pattern in pattern_variants:
            if re.match(pattern, line.strip(), flags=re.IGNORECASE):
                match_index = idx
                break
        if match_index is not None:
            break

    if match_index is None:
        return "Release notes available in CHANGELOG."

    collected: list[str] = []
    for line in lines[match_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            if collected:
                break
            continue
        if re.match(r"^v?\d", stripped):
            break
        if stripped.startswith("-") or stripped.startswith("*"):
            collected.append(stripped.lstrip("-* "))
        else:
            if not collected:
                collected.append(stripped)
            else:
                collected.append(stripped)
        if len(collected) >= 3:
            break

    summary = "; ".join(collected) if collected else "Release notes available in CHANGELOG."
    if len(summary) > limit:
        summary = summary[: limit - 1].rstrip() + "…"
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        action="append",
        help="Provider slug to update (codex, claude-code, gemini). Repeatable.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Persist changes to manifests (default: dry-run).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress details.",
    )
    args = parser.parse_args()

    if args.provider:
        targets = []
        for slug in args.provider:
            if slug not in PROVIDERS:
                parser.error(f"Unknown provider '{slug}'. Options: {', '.join(PROVIDERS)}")
            targets.append(PROVIDERS[slug])
    else:
        targets = list(PROVIDERS.values())

    any_errors = False
    for config in targets:
        try:
            update_provider(config, write=args.write, verbose=args.verbose)
        except RuntimeError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            any_errors = True

    if args.write and not any_errors:
        print("Provider manifests updated.")

    return 1 if any_errors else 0


if __name__ == "__main__":
    sys.exit(main())
