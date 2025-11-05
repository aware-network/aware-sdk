# Changelog

## 0.1.1 - 2025-10-29
- Added terminal handlers (create/session-resolve/bind-provider) under the kernel object tree with descriptor helpers and parity tests, enabling CLI/SDK consumers to rely on the canonical implementation.
- Agent-thread handlers now cover signup/login, orchestrating runtime session binding via the terminal helpers and unlocking kernel-first flows for CLI tests.
- Exposed `task.update-status` as a kernel handler that returns canonical plans (status diffs, overview updates, backlog entries), with tests covering the planning API.

## 0.1.0 - 2025-10-26
- Scaffolded package for concrete environments (kernel implementation pending).
