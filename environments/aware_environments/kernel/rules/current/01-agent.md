---
id: "02-agent-01-identity"
slug: "01-agent"
title: Rule 01 Agent Identity
status: template
layer: "agent"
author:
  agent: desktop-manager
  process: cli-rules
  thread: agent-cli-rules
aware_cli_version: 0.8.3
generated_at: '2025-10-25T23:34:48.851966Z'
source_template: templates/01-agent.md
---

# Rule 01 · Agent Identity

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

<!-- BEGIN CLI: function=agent:whoami checksum=a3b5a09e9042 -->
#### `whoami`
Inspect current agent/process/thread bindings for the session.
**Policy:** `object`
**Selectors:** _None_
**Flags:** _None_
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=agent:create-process checksum=d2bdec0bc30d -->
#### `create-process`
Ensure an agent process exists and return its metadata.
**Policy:** `object`
**Selectors:** `agent`
**Flags:** _None_
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=agent:create-thread checksum=9f6274dc8157 -->
#### `create-thread`
Create a new agent process thread filesystem scaffold.
**Policy:** `object`
**Selectors:** `agent`
**Flags:** _None_
**Hooks:** _None_
<!-- END CLI -->

## 3. Memory Responsibilities
### 3.1 Working Memory
- **Purpose:** persistent focus/objectives snapshot.
- **How:** `write-working` with rule references, receipts, task bindings.

<!-- BEGIN CLI: function=agent-thread-memory:write-working checksum=350adabc853e -->
#### `write-working`
Replace working memory content for the thread.
**Policy:** `04-agent-01-memory-hierarchy`
**Selectors:** `agent`, `process`, `thread`
**Flags:**
- `--identities-root PATH` — Override identities directory (default docs/identities).
- `--content TEXT` — Inline markdown body.
- `--content-file PATH` — Path to markdown body.
- `--author-agent NAME` — Override author agent.
- `--author-process NAME` — Override author process.
- `--author-thread NAME` — Override author thread.
**Hooks:** _None_
<!-- END CLI -->

### 3.2 Episodic Memory
- **Purpose:** immutable log of significant events, receipts, directives.

<!-- BEGIN CLI: function=agent-thread-memory:append-episodic checksum=d01518509390 -->
#### `append-episodic`
Add an episodic memory entry using canonical filename/timestamp.
**Policy:** `04-agent-01-memory-hierarchy`
**Selectors:** `agent`, `process`, `thread`
**Flags:**
- `--identities-root PATH` — Override identities directory (default docs/identities).
- `--title TEXT` — Episode title (required).
- `--content TEXT` — Inline markdown body.
- `--content-file PATH` — Path to markdown body.
- `--session-type TYPE` — Entry session type.
- `--significance LEVEL` — critical|high|medium|low.
- `--author-agent NAME` — Override author agent.
- `--author-process NAME` — Override author process.
- `--author-thread NAME` — Override author thread.
**Hooks:** _None_
<!-- END CLI -->

### 3.3 Memory Maintenance
- `status`, `history`, `diff`, `validate` keep memory consistent.

<!-- BEGIN CLI: function=agent-thread-memory:status checksum=8eece6c89c03 -->
#### `status`
Return working memory snapshot with latest episodic entries.
**Policy:** `04-agent-01-memory-hierarchy`
**Selectors:** `agent`, `process`, `thread`
**Flags:**
- `--identities-root PATH` — Override identities directory (default docs/identities).
- `--limit N` — Maximum episodic entries to include (default 5).
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=agent-thread-memory:history checksum=05964832c44d -->
#### `history`
List episodic entries with optional filters.
**Policy:** `04-agent-01-memory-hierarchy`
**Selectors:** `agent`, `process`, `thread`
**Flags:**
- `--identities-root PATH` — Override identities directory (default docs/identities).
- `--limit N` — Maximum episodic entries to include.
- `--significance LEVEL` — Filter by significance level.
- `--session-type TYPE` — Filter by session type.
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=agent-thread-memory:diff checksum=8b2134aa5aca -->
#### `diff`
List memory changes since the given timestamp.
**Policy:** `04-agent-01-memory-hierarchy`
**Selectors:** `agent`, `process`, `thread`
**Flags:**
- `--identities-root PATH` — Override identities directory (default docs/identities).
- `--since ISO` — Timestamp to compare from.
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=agent-thread-memory:validate checksum=5b06a9a31fe5 -->
#### `validate`
Check working/episodic files for presence (basic validation).
**Policy:** `04-agent-01-memory-hierarchy`
**Selectors:** `agent`, `process`, `thread`
**Flags:**
- `--identities-root PATH` — Override identities directory (default docs/identities).
**Hooks:** _None_
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
- Reference Rule 02 (Task lifecycle) and future conversation/thread rules for cross-context coordination.

## 7. Pending Enhancements
- CLI support for `actors` management, provider policies, and AGENTS.md identity preface (future work).

## 8. Validation Plan
- Render role bundles to ensure policy text embeds without warnings.
- Regenerate AGENTS.md after promotion; verify identity section appears above task/memory policies.
- Integrate with `aware-sdk init` once promoted and receipts validated.
