import json
from pathlib import Path

from importlib import resources

from aware_environments.kernel.objects.role import handlers as role_handlers


def _sample_payload() -> dict:
    resource = resources.files("aware_environments.kernel.samples.roles") / "role_registry.json"
    return json.loads(resource.read_text(encoding="utf-8"))


def test_role_import_and_policies(tmp_path: Path) -> None:
    identities_root = tmp_path / "docs" / "identities"
    payload = _sample_payload()
    role_slug = next(iter(payload["roles"]))
    result = role_handlers.import_handler(
        identities_root,
        payload=payload,
        mode="replace",
    )
    assert result["status"] == "updated"
    registry_path = Path(result["path"])
    assert registry_path.exists()

    policies = role_handlers.policies_handler(
        identities_root,
        role=role_slug,
        include_cli=True,
    )
    assert policies["role"] == role_slug
    assert "agent-thread-memory:status" in policies["policy_details"][0]["functions"]

    agents = role_handlers.agents_handler(identities_root, role=role_slug)
    assert agents["agents"] == ["codex"]

    export = role_handlers.export_handler(identities_root)
    assert role_slug in export["roles"]


def test_role_set_policy_replace(tmp_path: Path) -> None:
    identities_root = tmp_path / "docs" / "identities"
    payload = _sample_payload()
    role_slug = next(iter(payload["roles"]))
    role_handlers.import_handler(identities_root, payload=payload, mode="replace")

    update_payload = {
        "policies": ["02-task-01-lifecycle"],
        "agents": ["codex", "cursor"],
    }
    result = role_handlers.set_policy_handler(
        identities_root,
        role=role_slug,
        payload=update_payload,
        mode="replace",
    )
    assert result["status"] == "updated"

    policies = role_handlers.policies_handler(identities_root, role=role_slug)
    assert policies["policies"] == ["02-task-01-lifecycle"]
    agents = role_handlers.agents_handler(identities_root, role=role_slug)
    assert agents["agents"] == ["codex", "cursor"]


def test_list_roles(tmp_path: Path) -> None:
    identities_root = tmp_path / "docs" / "identities"
    payload = _sample_payload()
    role_slug = next(iter(payload["roles"]))
    role_handlers.import_handler(identities_root, payload=payload, mode="replace")
    roles = role_handlers.list_roles(identities_root)
    assert len(roles) == 1
    assert roles[0]["slug"] == role_slug
