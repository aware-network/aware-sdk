# aware-environment

`aware-environment` is the shared contract that lets humans and agents work on
the same project surface. It defines the dataclasses, registries, renderers,
and runtime helpers that every Aware environment (kernel or otherwise) uses to
publish Agents, Roles, Rules, Objects, and supporting protocols. Concrete
environments extend these building blocks, but the core contract shipped here
is what the CLI, release pipeline, and terminal automation expect.

## What ships in the package

- **Typed specs & registries** – immutable dataclasses describing agents,
  roles, rules, objects, and protocols plus registries for binding them to an
  environment.
- **Environment container & loader** – `Environment.empty()` returns a sterile
  registry bundle; `load_environment("module:get_environment")` imports a
  factory and returns a fully bound environment.
- **Runtime executor** – `ObjectExecutor` turns registered object functions
  into plan-executing calls that emit filesystem receipts/journals used by
  aware-cli and the release pipeline.
- **Filesystem helpers** – `OperationPlan`, receipt encoders, and pathspec
  utilities ensure object handlers produce deterministic diffs.
- **Documentation renderers** – constitution and environment guide renderers
  turn rule markdown into the human-facing guides consumed by AGENTS.md, CLAUDE
  overlays, and Studio panels.
- **ACL & seeding helpers** – utilities for modelling access control and
  generating the seed docs/panel manifests that environments expose.

## Quick start

```python
from aware_environment.agent.spec import AgentSpec
from aware_environment.environment import Environment
from aware_environment.object.spec import ObjectFunctionSpec, ObjectSpec
from aware_environment.role.spec import RoleSpec
from aware_environment.rule.spec import RuleSpec
from aware_environment.runtime.executor import FunctionCallRequest, ObjectExecutor

# Minimal constitution and role/agent wiring
env = Environment.empty()
env.bind_rules([
    RuleSpec(id="00-environment", title="Environment Constitution", markdown="# Welcome to Aware")
])
env.set_constitution_rule("00-environment")
env.bind_roles([
    RoleSpec(slug="environment-operator", title="Environment Operator", rule_ids=("00-environment",))
])
env.bind_agents([
    AgentSpec(slug="codex", title="Codex", role_slugs=("environment-operator",))
])

def ping(environment: Environment, message: str) -> dict[str, str]:
    return {"echo": message, "constitution": environment.get_constitution_rule().title}

env.bind_objects([
    ObjectSpec(
        type="hello",
        description="Example object",
        functions=(ObjectFunctionSpec(name="ping", handler_factory=lambda: ping),),
    )
])

executor = ObjectExecutor(env)
request = FunctionCallRequest(
    object_type="hello",
    function_name="ping",
    selectors={"agent": "codex"},
    arguments={"message": "Aware!"},
)
result = executor.execute(request)
print(result.payload["echo"])  # -> "Aware!"
```

The same executor is what aware-cli uses under the hood when an agent runs
`aware-cli object call`.

## Constitution-aware rendering

Environments can declare their governing rule with
`Environment.set_constitution_rule("00-environment")`. The renderer helpers
make it easy to surface that rule consistently:

- `render_constitution_summary(environment)` → markdown summary used in
  AGENTS.md and CLI overlays.
- `render_environment_guide(environment, heading_level=1)` → full environment
  guide (roles, rules, objects) generated as part of release pipelines.

If the constitution rule is missing, the renderer raises so CI catches drift.

## Integration points

- **aware-cli** loads the active environment with `load_environment` and routes
  every object/function call through `ObjectExecutor`, turning handler plans
  into receipts and journal entries.
- **Release/SDK pipelines** stage panel manifests, AGENTS.md bundles, and
  manifest locks using the environment renderers, ensuring humans and agents
  see the same instructions.
- **Custom environments** can extend the base registries, add protocols, or
  seed docs via `aware_environment.seed` while reusing the same runtime and
  filesystem guarantees.

## License

MIT © 2025 AWARE
