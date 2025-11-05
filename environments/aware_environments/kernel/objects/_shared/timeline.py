"""Timestamp helpers shared by process/thread adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
import re

_TIMESTAMP_IN_NAME = re.compile(r"(?P<stamp>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)", re.IGNORECASE)


def ensure_aware_datetime(value: Any) -> Optional[datetime]:
    """Alias retained for compatibility with CLI helpers."""

    return ensure_datetime(value)


def ensure_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (float, int)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        hyphenated = text.removesuffix("Z")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}", hyphenated):
            dt = datetime.strptime(hyphenated, "%Y-%m-%d-%H-%M-%S")
            return dt.replace(tzinfo=timezone.utc)

        iso_candidates = {
            text,
            text.replace(" ", "T"),
            text.replace("Z", "+00:00"),
            text.replace(" ", "T").replace("Z", "+00:00"),
        }
        for candidate in iso_candidates:
            try:
                dt = datetime.fromisoformat(candidate)
            except ValueError:
                continue
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text, fmt)
            except ValueError:
                continue
            return dt.replace(tzinfo=timezone.utc)
        return None

    return None


def document_timestamp(
    path: Path,
    metadata: Optional[dict[str, Any]] = None,
    *,
    extra_candidates: Iterable[Any] | None = None,
) -> datetime:
    metadata = metadata or {}
    for key in ("updated", "modified", "timestamp", "created"):
        value = metadata.get(key)
        normalized = ensure_datetime(value)
        if normalized:
            return normalized

    match = _TIMESTAMP_IN_NAME.search(path.name)
    if match:
        stamp = match.group("stamp")
        return datetime.strptime(stamp, "%Y-%m-%dT%H-%M-%SZ").replace(tz=timezone.utc)

    if extra_candidates:
        for candidate in extra_candidates:
            normalized = ensure_datetime(candidate)
            if normalized:
                return normalized

    return datetime.now(tz=timezone.utc)


__all__ = ["ensure_datetime", "ensure_aware_datetime", "document_timestamp"]
