from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

from aware_terminal.providers.manifest import (
    manifests_available,
    provider_manifests_root,
    provider_update_script,
)


@dataclass
class ProviderManifestStatus:
    status: str
    message: str
    age: Optional[timedelta]
    refreshed: bool = False
    timestamp: Optional[datetime] = None


class ProviderManifestRefresher:
    """Ensure provider release manifests are up to date before setup."""

    def __init__(
        self,
        *,
        providers_root: Optional[Path] = None,
        script_path: Optional[Path] = None,
    ) -> None:
        if providers_root is not None:
            self.providers_root = providers_root
        else:
            self.providers_root = provider_manifests_root() if manifests_available() else None
        self.script_path = script_path if script_path is not None else provider_update_script()

    def ensure_fresh(
        self,
        *,
        max_age: timedelta = timedelta(hours=6),
        allow_refresh: bool = True,
    ) -> ProviderManifestStatus:
        if self.providers_root is None or not self.providers_root.exists():
            return ProviderManifestStatus(
                status="bundled-missing",
                message="Provider manifests not bundled with this installation.",
                age=None,
                refreshed=False,
                timestamp=None,
            )

        age = self._manifest_age()
        if age is None:
            # No timestamps present; treat as bundled data without freshness signal.
            if allow_refresh and self._refresh():
                age = self._manifest_age()
                return ProviderManifestStatus(
                    status="refreshed",
                    message="Provider manifests refreshed.",
                    age=age,
                    refreshed=True,
                    timestamp=datetime.now(timezone.utc),
                )
            return ProviderManifestStatus(
                status="bundled",
                message="Using bundled provider manifests.",
                age=None,
                refreshed=False,
                timestamp=None,
            )

        if age <= max_age:
            return ProviderManifestStatus(
                status="fresh",
                message="Provider manifests are current.",
                age=age,
                refreshed=False,
                timestamp=datetime.now(timezone.utc) - age,
            )

        if not allow_refresh or self.script_path is None:
            return ProviderManifestStatus(
                status="stale",
                message="Provider manifests older than threshold; skipping auto refresh.",
                age=age,
                refreshed=False,
                timestamp=datetime.now(timezone.utc) - age,
            )

        if self._refresh():
            new_age = self._manifest_age()
            return ProviderManifestStatus(
                status="refreshed",
                message="Provider manifests refreshed.",
                age=new_age,
                refreshed=True,
                timestamp=datetime.now(timezone.utc),
            )

        return ProviderManifestStatus(
            status="error",
            message="Failed to refresh provider manifests.",
            age=age,
            refreshed=False,
            timestamp=datetime.now(timezone.utc) - age,
        )

    def _manifest_age(self) -> Optional[timedelta]:
        timestamps = []
        for manifest_path in self.providers_root.glob("*/releases.json"):
            info = self._parse_manifest_timestamp(manifest_path)
            if info:
                timestamps.append(info)
        if not timestamps:
            return None
        latest = max(timestamps)
        return datetime.now(timezone.utc) - latest

    def _parse_manifest_timestamp(self, path: Path) -> Optional[datetime]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        channels: Dict[str, Dict[str, str]] = data.get("channels", {})  # type: ignore[assignment]
        newest: Optional[datetime] = None
        for channel in channels.values():
            if not isinstance(channel, dict):
                continue
            updated_at = channel.get("updated_at")
            if not updated_at:
                continue
            try:
                ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except Exception:
                continue
            if newest is None or ts > newest:
                newest = ts
        return newest

    def _refresh(self) -> bool:
        if self.script_path is None or not self.script_path.exists():
            return False
        allowing_network = os.environ.get("AWARE_TERMINAL_ALLOW_MANIFEST_REFRESH", "1") == "1"
        if not allowing_network:
            return False
        try:
            result = subprocess.run(
                [sys.executable, str(self.script_path)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception:
            return False
        return result.returncode == 0
