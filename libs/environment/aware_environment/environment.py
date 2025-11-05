"""Environment container aggregating agents, roles, rules, and objects."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Iterable

from .agent.registry import AgentRegistry
from .agent.spec import AgentSpec
from .exceptions import EnvironmentLoadError
from .object.registry import ObjectRegistry
from .object.spec import ObjectSpec
from .role.registry import RoleRegistry
from .role.spec import RoleSpec
from .rule.registry import RuleRegistry
from .rule.spec import RuleSpec
from .protocol.registry import ProtocolRegistry
from .protocol.spec import ProtocolSpec


@dataclass
class Environment:
    """Container aggregating agent, role, rule, and object registries."""

    agents: AgentRegistry
    roles: RoleRegistry
    rules: RuleRegistry
    objects: ObjectRegistry
    protocols: ProtocolRegistry
    constitution_rule_id: str | None = None

    @classmethod
    def empty(cls) -> "Environment":
        return cls(
            AgentRegistry(),
            RoleRegistry(),
            RuleRegistry(),
            ObjectRegistry(),
            ProtocolRegistry(),
            constitution_rule_id=None,
        )

    def set_constitution_rule(self, rule_id: str | None) -> None:
        self.constitution_rule_id = rule_id

    def get_constitution_rule(self) -> RuleSpec | None:
        if not self.constitution_rule_id:
            return None
        try:
            return self.rules.get(self.constitution_rule_id)
        except Exception:
            return None

    def bind_agents(self, specs: Iterable[AgentSpec]) -> None:
        self.agents.register_many(specs)

    def bind_roles(self, specs: Iterable[RoleSpec]) -> None:
        self.roles.register_many(specs)

    def bind_rules(self, specs: Iterable[RuleSpec]) -> None:
        self.rules.register_many(specs)

    def bind_objects(self, specs: Iterable[ObjectSpec]) -> None:
        self.objects.register_many(specs)

    def bind_protocols(self, specs: Iterable[ProtocolSpec]) -> None:
        self.protocols.register_many(specs)

    def get_protocol(self, slug: str) -> ProtocolSpec:
        return self.protocols.get(slug)


def load_environment(import_path: str) -> Environment:
    """Import `module:get_environment` style path and return the environment."""

    if ":" not in import_path:
        raise EnvironmentLoadError("Environment import path must be 'module:get_environment'")

    module_name, attr = import_path.split(":", 1)
    module = importlib.import_module(module_name)
    factory = getattr(module, attr, None)
    if callable(factory):
        env = factory()
        if not isinstance(env, Environment):  # pragma: no cover - defensive
            raise EnvironmentLoadError(f"Factory '{import_path}' did not return an Environment instance")
        return env
    raise EnvironmentLoadError(f"Environment factory '{import_path}' not found")
