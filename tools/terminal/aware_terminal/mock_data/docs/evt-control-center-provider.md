# Control Center Data Provider Design (Excerpt)

* Design note summarising the provider interface for mock data *

- Define `EnvironmentInfo`, `ProcessInfo`, `ThreadInfo` dataclasses.
- Introduce `ControlDataProvider` protocol with list/get operations.
- Provide mock fixtures so the Control Center TUI can be built ahead of the CLI integration.
