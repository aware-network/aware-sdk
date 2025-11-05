#!/usr/bin/env python3
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

def _provider_root() -> Path:
    env_override = os.environ.get('AWARE_TERMINAL_MANIFEST_ROOT')
    if env_override:
        return Path(env_override).expanduser().resolve()
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / 'libs' / 'providers' / 'terminal' / 'aware_terminal_providers' / 'providers'

def main() -> int:
    root = _provider_root()
    if not root.exists():
        return 0
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    for manifest_path in root.glob('*/releases.json'):
        try:
            data = json.loads(manifest_path.read_text(encoding='utf-8'))
        except Exception:
            data = {'provider': manifest_path.parent.name, 'channels': {}}
        channels = data.setdefault('channels', {})
        if not isinstance(channels, dict):
            channels = {}
            data['channels'] = channels
        if not channels:
            channels['latest'] = {}
        for channel in channels.values():
            if isinstance(channel, dict):
                channel['updated_at'] = timestamp
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
