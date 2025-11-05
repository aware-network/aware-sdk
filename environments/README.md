# aware-environments (workspace package)

This package hosts concrete environment implementations built on top of
`aware_environment`. The initial environment is `kernel`, which defines the
core agents, roles, rules, and objects used by aware-sdk and the CLI.

Downstream packages (aware-sdk, aware-cli) import the kernel registry to render
AGENTS.md, seed rules, and expose CLI objects.
