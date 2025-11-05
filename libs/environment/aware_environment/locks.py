"""Helpers to compute environment lock files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from .environment import Environment


def compute_env_lock(env_name: str, kernel_ref: str, version: str, environment: Environment) -> Dict[str, Any]:
    payload = {
        "environment": env_name,
        "kernel_ref": kernel_ref,
        "version": version,
        "spec_hash": _hash_environment(environment),
    }
    return payload


def compute_rules_lock(environment: Environment) -> Dict[str, Any]:
    entries = []
    for rule in environment.rules.list():
        rule_path = Path(rule.path)
        digest = None
        if rule_path.exists():
            digest = _sha256(rule_path.read_bytes())
        entries.append({
            "id": rule.id,
            "title": rule.title,
            "layer": rule.layer,
            "hash": digest,
        })
    return {"rules": entries}


def _hash_environment(environment: Environment) -> str:
    serialised = {
        "agents": [spec.slug for spec in environment.agents.list()],
        "roles": [spec.slug for spec in environment.roles.list()],
        "rules": [spec.id for spec in environment.rules.list()],
        "objects": [spec.type for spec in environment.objects.list()],
    }
    data = json.dumps(serialised, sort_keys=True).encode("utf-8")
    return _sha256(data)


def _sha256(data: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(data)
    return hasher.hexdigest()
