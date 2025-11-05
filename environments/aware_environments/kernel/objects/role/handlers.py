"""Kernel handlers for role registry operations."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import yaml


ROLE_REGISTRY_ENV = "AWARE_ROLE_REGISTRY_PATH"
REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_ROLE_REGISTRY_PATH = REPO_ROOT / "docs" / "identities" / "_registry" / "role_registry.json"


def _resolve_registry_path(
    identities_root: Optional[Path],
    registry_path: Optional[Path],
) -> Path:
    if registry_path:
        return Path(registry_path).expanduser().resolve()
    if identities_root:
        identities_root = Path(identities_root).expanduser().resolve()
        return identities_root / "_registry" / "role_registry.json"
    env_value = os.getenv(ROLE_REGISTRY_ENV)
    if env_value:
        return Path(env_value).expanduser().resolve()
    return DEFAULT_ROLE_REGISTRY_PATH


def _ensure_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_registry(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"generated_at": None, "roles": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in role registry at {path}: {exc}") from exc
    roles = data.get("roles")
    if not isinstance(roles, dict):
        roles = {}
    return {
        "generated_at": data.get("generated_at"),
        "roles": roles,
    }


def _write_registry(path: Path, registry: Dict[str, Any]) -> None:
    payload = {
        "generated_at": registry.get("generated_at"),
        "roles": registry.get("roles", {}),
    }
    _ensure_directory(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _role_payload_to_output(slug: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    title = payload.get("title") or slug.replace("-", " ").title()
    description = payload.get("description")
    policies = list(payload.get("policies", []))
    agents = list(payload.get("agents", []))

    cli_objects: List[Dict[str, Any]] = []
    cli_payload = payload.get("cli", {})
    if isinstance(cli_payload, dict):
        objects_map = cli_payload.get("objects", {})
        if isinstance(objects_map, dict):
            for object_name, functions in objects_map.items():
                cli_objects.append(
                    {
                        "object": object_name,
                        "functions": list(functions) if isinstance(functions, Iterable) else [],
                    }
                )

    policy_details_payload = payload.get("policy_details", [])
    policy_details: List[Dict[str, Any]] = []
    if isinstance(policy_details_payload, list):
        for detail in policy_details_payload:
            if not isinstance(detail, dict):
                continue
            rule_id = str(detail.get("rule_id", "")).strip()
            if not rule_id:
                continue
            functions = [str(function).strip() for function in detail.get("functions", []) if str(function).strip()]
            extras = [str(extra).strip() for extra in detail.get("extras", []) if str(extra).strip()]
            policy_details.append(
                {
                    "rule_id": rule_id,
                    "functions": functions,
                    "extras": extras,
                    "title": detail.get("title"),
                    "include_policy_text": bool(detail.get("include_policy_text", False)),
                    "section": str(detail.get("section")).strip() if detail.get("section") else None,
                }
            )

    return {
        "id": str(payload.get("id", slug)),
        "slug": slug,
        "title": title,
        "description": description,
        "policies": policies,
        "cli_objects": cli_objects,
        "agents": agents,
        "policy_details": policy_details,
    }


def _list_roles_internal(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    roles_payload = registry.get("roles", {})
    if not isinstance(roles_payload, dict):
        return []
    roles: List[Dict[str, Any]] = []
    for slug, payload in roles_payload.items():
        if not isinstance(payload, dict):
            continue
        roles.append(_role_payload_to_output(slug, payload))
    roles.sort(key=lambda role: role["slug"])
    return roles


def list_roles(
    identities_root: Optional[Path] = None,
    *,
    registry_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    path = _resolve_registry_path(identities_root, registry_path)
    registry = _load_registry(path)
    return _list_roles_internal(registry)


def _load_role(
    registry: Dict[str, Any],
    slug: str,
) -> Tuple[str, Dict[str, Any]]:
    roles_payload = registry.get("roles", {})
    if not isinstance(roles_payload, dict):
        raise ValueError("Role registry is malformed; expected roles object.")

    normalized_slug = slug.lower()
    for candidate_slug, payload in roles_payload.items():
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("id", candidate_slug))
        if candidate_slug == normalized_slug or candidate_id == slug:
            return candidate_slug, payload
    raise ValueError(f"Role '{slug}' not found in registry.")


def policies_handler(
    identities_root: Optional[Path] = None,
    *,
    registry_path: Optional[Path] = None,
    role: str,
    include_cli: bool = False,
) -> Dict[str, Any]:
    path = _resolve_registry_path(identities_root, registry_path)
    registry = _load_registry(path)
    slug, payload = _load_role(registry, role)
    role_output = _role_payload_to_output(slug, payload)
    result = {
        "role": role_output["slug"],
        "title": role_output["title"],
        "description": role_output["description"],
        "policies": role_output["policies"],
    }
    if include_cli:
        result["cli_objects"] = role_output["cli_objects"]
        result["policy_details"] = role_output["policy_details"]
    return result


def agents_handler(
    identities_root: Optional[Path] = None,
    *,
    registry_path: Optional[Path] = None,
    role: str,
) -> Dict[str, Any]:
    path = _resolve_registry_path(identities_root, registry_path)
    registry = _load_registry(path)
    slug, payload = _load_role(registry, role)
    role_output = _role_payload_to_output(slug, payload)
    return {
        "role": role_output["slug"],
        "agents": role_output["agents"],
    }


def export_handler(
    identities_root: Optional[Path] = None,
    *,
    registry_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = _resolve_registry_path(identities_root, registry_path)
    registry = _load_registry(path)
    payload = {
        "path": str(path),
        "generated_at": registry.get("generated_at"),
        "roles": registry.get("roles", {}),
    }

    if output_path is not None:
        output_path = Path(output_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload = dict(payload)
        payload["output_path"] = str(output_path)

    return payload


def _deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_structured_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Role registry payload must be an object.")
    return payload


def _registry_from_payload(payload: Dict[str, Any], *, generated_at: str) -> Dict[str, Any]:
    registry = _load_structured_input(payload)
    if "roles" not in registry:
        registry["roles"] = {}
    if not isinstance(registry["roles"], dict):
        raise ValueError("Registry payload must include a 'roles' object.")
    registry["generated_at"] = generated_at
    return registry


def _merge_registry(existing: Dict[str, Any], updates: Dict[str, Any], *, generated_at: str) -> Dict[str, Any]:
    if not isinstance(updates.get("roles"), dict):
        raise ValueError("Registry merge payload must include a 'roles' object.")

    existing_roles = existing.get("roles")
    if not isinstance(existing_roles, dict):
        existing_roles = {}

    merged_roles = dict(existing_roles)
    for slug, payload in updates["roles"].items():
        if not isinstance(payload, dict):
            raise ValueError(f"Role entry '{slug}' must be an object.")
        if slug in merged_roles:
            merged_roles[slug] = _deep_merge(merged_roles[slug], payload)
        else:
            merged_roles[slug] = dict(payload)
        merged_roles[slug].setdefault("slug", slug)

    return {
        "generated_at": generated_at,
        "roles": merged_roles,
    }


def _update_role_payload(
    registry: Dict[str, Any],
    slug: str,
    updates: Dict[str, Any],
    *,
    generated_at: str,
    merge: bool,
) -> Dict[str, Any]:
    roles = registry.get("roles")
    if not isinstance(roles, dict):
        raise ValueError("Role registry is malformed; expected 'roles' object.")
    if slug not in roles:
        raise ValueError(f"Role '{slug}' not found in registry.")

    current_payload = roles[slug]
    if not isinstance(current_payload, dict):
        raise ValueError(f"Role payload for '{slug}' is not an object.")

    if merge:
        candidate_payload = _deep_merge(current_payload, updates)
    else:
        candidate_payload = dict(updates)
    candidate_payload.setdefault("id", current_payload.get("id"))
    candidate_payload.setdefault("slug", slug)

    updated = dict(roles)
    updated[slug] = candidate_payload
    return {
        "generated_at": generated_at,
        "roles": updated,
    }


def import_handler(
    identities_root: Optional[Path] = None,
    *,
    registry_path: Optional[Path] = None,
    payload: Dict[str, Any] | str,
    mode: str = "replace",
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    path = _resolve_registry_path(identities_root, registry_path)
    timestamp = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"
    if mode not in {"replace", "merge"}:
        raise ValueError("Mode must be 'replace' or 'merge'.")

    if isinstance(payload, str):
        payload = json.loads(payload)

    if mode == "replace":
        registry = _registry_from_payload(payload, generated_at=timestamp)
    else:
        existing = _load_registry(path)
        registry = _merge_registry(
            existing, _registry_from_payload(payload, generated_at=timestamp), generated_at=timestamp
        )

    _write_registry(path, registry)
    return {
        "status": "updated",
        "mode": mode,
        "path": str(path),
        "roles": sorted(registry.get("roles", {}).keys()),
    }


def set_policy_handler(
    identities_root: Optional[Path] = None,
    *,
    registry_path: Optional[Path] = None,
    role: str,
    payload: Dict[str, Any] | str,
    mode: str = "merge",
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    if mode not in {"merge", "replace"}:
        raise ValueError("Mode must be 'merge' or 'replace'.")
    path = _resolve_registry_path(identities_root, registry_path)
    timestamp = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"
    if isinstance(payload, str):
        payload = json.loads(payload)

    registry = _load_registry(path)
    updated = _update_role_payload(
        registry,
        role,
        payload,
        generated_at=timestamp,
        merge=(mode == "merge"),
    )
    _write_registry(path, updated)
    return {
        "status": "updated",
        "role": role,
        "mode": mode,
        "path": str(path),
    }


def load_payload_from_file(path: Path) -> Dict[str, Any]:
    """Utility used by CLI fallback to parse JSON or YAML payloads."""

    content = path.read_text(encoding="utf-8")
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        if not yaml:
            raise ValueError(f"Failed to parse {path}: invalid JSON and PyYAML unavailable.")
        data = yaml.safe_load(content)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected object at root of {path}.")
    return data


__all__ = [
    "list_roles",
    "policies_handler",
    "agents_handler",
    "export_handler",
    "import_handler",
    "set_policy_handler",
    "load_payload_from_file",
]
