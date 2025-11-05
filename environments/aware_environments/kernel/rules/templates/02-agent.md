---
id: "02-agent-01-identity"
slug: "02-agent"
title: "Rule 02 Agent Identity"
status: "template"
layer: "agent"
author:
  agent: desktop-manager
  process: cli-rules
  thread: agent-cli-rules
---

# Rule 02 · Agent Identity

## 1. Identity Hierarchy
| Layer | Description | Required metadata | CLI source |
| --- | --- | --- | --- |
| Agent | Personality & policy bundle | `agent.slug`, `agent.uuid`, roles, policies | `aware-cli object call --type agent --function status` |
| Process | Long-running capability scope (e.g., `cli-rules`) | `process.slug`, `process.uuid`, associated agent | `aware-cli object call --type agent --function create-process` |
| Thread | Execution context bound to objects (tasks, conversations, terminals) | `thread.slug`, `thread.uuid`, branch manifests | `aware-cli object call --type agent --function create-thread` |
| Actor | Human or automated participant attached to the thread | `actor.kind`, `actor.slug`, permissions | `aware-cli object call --type agent --function actors` *(future)* |

- **Actor types:**
  - `human` — interactive operator or observer.
  - `agent` — automated participant following these rules.
  - `provider` — external capability; policies pending.

## 2. Identity Commands
- `whoami` — inspect bindings for the current session.
- `status` — view agent metadata and registered processes/threads.
- `create-process` — provision or fetch an agent process scaffold.
- `create-thread` — create a thread under a process with role bindings.

<!-- BEGIN CLI: function=agent:whoami -->
<!-- END CLI -->

<!-- BEGIN CLI: function=agent:create-process -->
<!-- END CLI -->

<!-- BEGIN CLI: function=agent:create-thread -->
<!-- END CLI -->

## 3. Memory Responsibilities
### 3.1 Working Memory
- **Purpose:** persistent focus/objectives snapshot.
- **How:** `write-working` with rule references, receipts, task bindings.

<!-- BEGIN CLI: function=agent-thread-memory:write-working -->
<!-- END CLI -->

### 3.2 Episodic Memory
- **Purpose:** immutable log of significant events, receipts, directives.

<!-- BEGIN CLI: function=agent-thread-memory:append-episodic -->
<!-- END CLI -->

### 3.3 Memory Maintenance
- `status`, `history`, `diff`, `validate` keep memory consistent.

<!-- BEGIN CLI: function=agent-thread-memory:status -->
<!-- END CLI -->

<!-- BEGIN CLI: function=agent-thread-memory:history -->
<!-- END CLI -->

<!-- BEGIN CLI: function=agent-thread-memory:diff -->
<!-- END CLI -->

<!-- BEGIN CLI: function=agent-thread-memory:validate -->
<!-- END CLI -->

## 4. Identity & Memory Invariants
- Run `whoami` (or confirm cached bindings) before mutating tasks or memory; store the receipt ID.
- Working memory header must track `agent`, `process`, `thread`, and `actor` fields consistent with latest `whoami` output.
- Reference receipts (`.aware/receipts/identity/...`) in working/episodic entries; treat receipts as ground truth.
- Record `actor:<slug>` markers in episodic memory; halt when identity mismatches occur.
- On `whoami` failure, log the error, pause task updates, and escalate.

## 5. Receipts & Logging
- Identity-affecting commands must emit receipts.
- Recommended flow: create-thread → update working memory → append episodic summary.

## 6. Interactions with Tasks & Threads
- Working memory must include bound task doc IDs.
- Thread manifests list bound objects so Control Center/Studio can hydrate context.
- Reference Rule 03 (Task lifecycle) and future conversation/thread rules for cross-context coordination.

## 7. Pending Enhancements
- CLI support for `actors` management, provider policies, and AGENTS.md identity preface (future work).

## 8. Validation Plan
- Render role bundles to ensure policy text embeds without warnings.
- Regenerate AGENTS.md after promotion; verify identity section appears above task/memory policies.
- Integrate with `aware-sdk init` once promoted and receipts validated.
