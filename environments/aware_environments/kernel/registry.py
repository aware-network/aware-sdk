"""Kernel environment registry."""

from aware_environment import Environment
from aware_environment.object.metadata import ensure_paths_metadata

from .agents import AGENTS
from .roles import ROLES
from .rules import RULES
from .protocols import PROTOCOLS
from .objects import OBJECTS


def get_environment() -> Environment:
    """Return the kernel environment with registered specs."""

    env = Environment.empty()
    env.bind_agents(AGENTS)
    env.bind_roles(ROLES)
    env.bind_rules(RULES)
    env.bind_objects(tuple(ensure_paths_metadata(spec) for spec in OBJECTS))
    env.bind_protocols(PROTOCOLS)
    env.set_constitution_rule("00-environment-constitution")
    return env


__all__ = ["get_environment"]
