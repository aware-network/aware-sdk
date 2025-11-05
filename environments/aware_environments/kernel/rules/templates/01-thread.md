---
id: "01-thread-01-runtime"
slug: "01-thread"
title: "Rule 01 Thread Runtime"
status: "template"
layer: "environment"
author:
  agent: aware-manager
  process: orchestrator
  thread: thread-6aef767c
---

# Rule 01 · Thread Runtime

Thread is the canonical orchestration surface inside the kernel. Every receipt, pane, and participant is routed through a thread directory under `docs/runtime/process/<process>/threads/<thread>/`.

## 1. Thread Lifecycle
| Phase | Purpose | CLI Function | Key Pathspecs |
| --- | --- | --- | --- |
| Discover | List available threads grouped by process | `aware-cli object list --type thread [--process <slug>]` | `thread_dir` |
| Inspect | Fetch metadata + branches for a specific thread | `aware-cli object call --type thread --id <process/thread|uuid> --function status` | `thread_manifest`, `thread_branches` |
| Observe activity | Tail backlog / conversation events (FS lane) | `aware-cli object call --type thread --id <identifier> --function activity --since <iso>` | `thread_backlog`, `thread_conversations_dir` |
| Manage branches | Bind/migrate/refresh pane manifests (task, conversation, ocg, terminal) | `branch-set`, `branch-migrate`, `branch-refresh` | `thread_branches`, `thread_pane_manifests` |
| Bind participants | Attach agents/humans/services to the orchestration surface | `participants-bind`, `participants-update`, `participants-list` | `thread_participants` |

## 2. Required Layout
```
docs/runtime/process/<process>/threads/<thread>/
├─ thread.json              # metadata (title, description, uuid, created_at)
├─ participants.json        # maintained via participants-bind/update
├─ branches/<pane>/<id>.json
├─ pane_manifests/<pane>/<id>.json
├─ conversations/*.md
├─ backlog/YYYY-MM-DD.md
└─ repository/…             # optional branch-linked repo metadata
```

Thread functions emitted by the kernel expect this structure. CLI helpers refuse to write when manifests drift or receipts are missing.

## 3. CLI Functions

### Discovery & Status
- `list` — enumerate threads (optionally filtered by process).
- `status` — return metadata plus branch summary.
- `activity` — collate backlog + conversation updates after `--since`.
- `branches` / `pane-manifest` — inspect pane bindings.
- `conversations` / `doc` — read thread-scoped markdown artifacts.

<!-- BEGIN CLI: function=thread:list -->
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:status -->
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:activity -->
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:branches -->
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:pane-manifest -->
<!-- END CLI -->

### Branch Binding
- `branch-set` — write or update a single pane branch payload.
- `branch-migrate` — lift legacy single-file manifests into branch layout.
- `branch-refresh` — touch a branch + manifest to update timestamps or regenerate computed payloads.

<!-- BEGIN CLI: function=thread:branch-set -->
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:branch-migrate -->
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:branch-refresh -->
<!-- END CLI -->

### Participants
- `participants-bind` — attach or replace a participant entry. Accepts inline JSON; CLI will coerce arguments for `--apt-id`, `--agent-thread`, `--human-id`, etc.
- `participants-update` — mutate status/session metadata for an existing participant ID.
- `participants-list` — list participants with optional `--type`, `--status`, or `--participant-id` filters; `--json` returns raw manifest.

<!-- BEGIN CLI: function=thread:participants-bind -->
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:participants-update -->
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:participants-list -->
<!-- END CLI -->

## 4. Receipts & Compliance
- Every branch or participant write emits a receipt (Rule 06 compliance pending full Triptych integration). CLI enforces `--force` for replacements to avoid silent drift.
- The manifest timestamp is updated automatically; Studio/agents rely on `updated_at` to refresh panes in FS fallback mode.

## 5. Coordination Patterns
- **Thread selection** precedes task or conversation creation. Use `list`/`status` to confirm context before calling Task/Conversation functions.
- **Pane registration**: call `branch-set` (or `branch-migrate`) immediately after a new object is created to keep Desktop panes synced.
- **Participant binding**: run `participants-bind` after agent bootstrap (Rule 01) so receipts, terminals, and panes can reference the correct actor.

## 6. Residual Work
- Auto-bind threads during CLI `agent-thread login` currently bridges participants via inline handler. Promote to standalone `thread.participants-bind` invocation once CLI arguments are fully wired.
- Extend receipts to include `thread_id`, `op_id`, `fs_ops[]` for Studio delta watchers.
- Document Terminal integration (`terminal.*` functions) once the default providers register via thread descriptors.
