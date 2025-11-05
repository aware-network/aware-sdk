"""Helpers for fragment markers embedded in rule templates."""

from __future__ import annotations

from typing import Dict, Iterable, Tuple

BEGIN_MARKER = "<!-- BEGIN CLI:"
END_MARKER = "<!-- END CLI -->"


def parse_begin_marker(marker: str) -> Dict[str, str]:
    """Parse a BEGIN marker into attribute dictionary."""

    if not marker.startswith(BEGIN_MARKER) or not marker.strip().endswith("-->"):
        raise ValueError("Invalid CLI begin marker format.")
    body = marker[len(BEGIN_MARKER) :].strip()
    if not body.endswith("-->"):
        raise ValueError("Invalid CLI begin marker format.")
    body = body[:-3].strip()
    if not body:
        raise ValueError("CLI begin marker is missing attributes.")

    attributes: Dict[str, str] = {}
    for token in body.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        attributes[key.strip()] = value.strip()
    if not attributes:
        raise ValueError("CLI begin marker is missing attributes.")
    return attributes


def format_begin_marker(attributes: Dict[str, str]) -> str:
    """Format a BEGIN marker preserving preferred key ordering."""

    preferred_order: Tuple[str, ...] = ("object", "function", "rule", "role", "checksum")
    seen: set[str] = set()
    parts: list[str] = []
    for key in preferred_order:
        if key in attributes:
            parts.append(f"{key}={attributes[key]}")
            seen.add(key)
    for key in sorted(attributes.keys()):
        if key in seen:
            continue
        parts.append(f"{key}={attributes[key]}")
    suffix = " ".join(parts)
    return f"{BEGIN_MARKER} {suffix} -->"


__all__ = ["BEGIN_MARKER", "END_MARKER", "parse_begin_marker", "format_begin_marker"]
