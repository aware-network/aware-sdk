---
title: APT Bootstrap Protocol
status: current
version: "0.1"
source_template: templates/apt-bootstrap.md
generated_at: '2025-10-31T05:50:00Z'
---

# APT Bootstrap Protocol

## When to Use
- An agent session starts without a bound APT (Agent · Process · Thread).
- Identity artifacts (`agent.json`, process/thread manifests) are missing or stale.
- Studio or CLI needs to decide between reusing or creating identity scaffolds before work begins.

## Decision Tree
1. **Discovery** — Inspect existing agent/process/thread manifests and capture receipts for current state.
2. **Evaluation** — Prefer reuse when manifests are consistent; otherwise prepare to create new scaffolds.
3. **Decision** — Choose between reuse (session update) or creation (signup) based on Rule 01 policy checks.
4. **Execution** — Execute operations in receipt-first order and regenerate guides to broadcast the new state.

## Key Outcomes
- Active APT with up-to-date manifests and global guides.
- Receipts recorded in task coordination artifacts.
- Clear follow-up actions aligned with Rule 01 and Rule 02.

## Supporting Rules
- Rule 00 · Environment Constitution
- Rule 01 · Agent Identity
- Rule 02 · Task Lifecycle

## Examples
- Reuse identity:
  ```bash
  aware-cli object call --type agent-thread --function session-update --id aware-manager/main/thread-object-agent
  aware-cli object call --type environment --function render-guide --id kernel --aware-root .
  ```
- Create identity:
  ```bash
  aware-cli object call --type agent --function signup --agent aware-manager --process main
  aware-cli object call --type agent-thread --function signup --id aware-manager/main/thread-object-agent
  aware-cli object call --type environment --function render-guide --id kernel --aware-root .
  ```

