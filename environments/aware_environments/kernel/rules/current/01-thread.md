## Rule 01 Thread Runtime
## Rule 01 Thread Runtime
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

<!-- BEGIN CLI: function=thread:list checksum=7e5fe4a89ecb -->
#### `list`
list function for thread
**Policy:** `01-thread-01-runtime`
**Selectors:** `process`
**Flags:**
- ``--runtime-root`` — Override runtime root.
- ``--process`` — Process slug filter.
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:status checksum=32f900cedd68 -->
#### `status`
status function for thread
**Policy:** `01-thread-01-runtime`
**Selectors:** `process`, `thread`
**Flags:**
- ``--runtime-root`` — Override runtime root.
- ``--process`` — Process slug.
- ``--thread`` — Thread slug.
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:activity checksum=604c3212e05f -->
#### `activity`
activity function for thread
**Policy:** `01-thread-01-runtime`
**Selectors:** `process`, `thread`
**Flags:**
- ``--runtime-root`` — Override runtime root.
- ``--process`` — Process slug.
- ``--thread`` — Thread slug.
- ``--since`` — ISO timestamp to filter activity.
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:branches checksum=a8eac5d04b88 -->
#### `branches`
branches function for thread
**Policy:** `01-thread-01-runtime`
**Selectors:** `process`, `thread`
**Flags:**
- ``--runtime-root`` — Override runtime root.
- ``--process`` — Process slug.
- ``--thread`` — Thread slug.
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:pane-manifest checksum=ec49f7a56fab -->
#### `pane-manifest`
pane-manifest function for thread
**Policy:** `01-thread-01-runtime`
**Selectors:** `process`, `thread`
**Flags:**
- ``--runtime-root`` — Override runtime root.
- ``--process`` — Process slug.
- ``--thread`` — Thread slug.
- ``--pane`` — Pane kind (task, conversation, terminal, etc.). [required]
- ``--branch-id`` — Branch identifier (defaults to pane slug when omitted).
**Hooks:** _None_
<!-- END CLI -->

### Branch Binding
- `branch-set` — write or update a single pane branch payload.
- `branch-migrate` — lift legacy single-file manifests into branch layout.
- `branch-refresh` — touch a branch + manifest to update timestamps or regenerate computed payloads.

<!-- BEGIN CLI: function=thread:branch-set checksum=b7118b726be5 -->
#### `branch-set`
branch-set function for thread
**Policy:** `01-thread-01-runtime`, `02-task-03-change-tracking`
**Selectors:** `process`, `thread`
**Flags:**
- ``--runtime-root`` — Override runtime root.
- ``--process`` — Process slug.
- ``--thread`` — Thread slug.
- ``--pane`` — Pane kind to bind. [required]
- ``--task`` — Task identifier <project>/<task> to bind.
- ``--projects-root`` — Override docs/projects root.
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:branch-migrate checksum=75d186f240b3 -->
#### `branch-migrate`
branch-migrate function for thread
**Policy:** `01-thread-01-runtime`, `02-task-03-change-tracking`
**Selectors:** `process`, `thread`
**Flags:**
- ``--runtime-root`` — Override runtime root.
- ``--process`` — Process slug.
- ``--thread`` — Thread slug.
- ``--pane`` — Pane kind to migrate. [required]
- ``--conversation`` — Conversation identifier to migrate.
- ``--task`` — Task identifier <project>/<task> to migrate.
- ``--projects-root`` — Override docs/projects root.
- ``--migrate-singleton`` — Migrate legacy singleton manifests into per-branch layout. (default: False)
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:branch-refresh checksum=98cf72a2b248 -->
#### `branch-refresh`
branch-refresh function for thread
**Policy:** `01-thread-01-runtime`, `02-task-03-change-tracking`
**Selectors:** `process`, `thread`
**Flags:**
- ``--runtime-root`` — Override runtime root.
- ``--process`` — Process slug.
- ``--thread`` — Thread slug.
- ``--pane`` — Pane kind to refresh. [required]
- ``--branch-id`` — Optional branch identifier.
**Hooks:** _None_
<!-- END CLI -->

### Participants
- `participants-bind` — attach or replace a participant entry. Accepts inline JSON; CLI will coerce arguments for `--apt-id`, `--agent-thread`, `--human-id`, etc.
- `participants-update` — mutate status/session metadata for an existing participant ID.
- `participants-list` — list participants with optional `--type`, `--status`, or `--participant-id` filters; `--json` returns raw manifest.

<!-- BEGIN CLI: function=thread:participants-bind checksum=0278e339f38c -->
#### `participants-bind`
participants-bind function for thread
**Policy:** `01-thread-01-runtime`, `02-task-03-change-tracking`
**Selectors:** `process`, `thread`
**Flags:**
- ``--runtime-root`` — Override runtime root.
- ``--process`` — Process slug.
- ``--thread`` — Thread slug.
- ``--participant-type`` — Participant type (agent|human|organization|service).
- ``--participant-id`` — Override participant identifier (defaults to derived slug or UUID).
- ``--agent-thread`` — Agent/process/thread slug (when participant-type=agent).
- ``--apt-id`` — Agent process thread UUID (when participant-type=agent).
- ``--human-id`` — Human UUID (when participant-type=human).
- ``--organization-id`` — Organization UUID (when participant-type=organization).
- ``--service-id`` — Service UUID (when participant-type=service).
- ``--role`` — Participant role (executor|controller|observer|other).
- ``--status`` — Participant status (attached|detached|released|errored|pending).
- ``--session-state`` — Session state (running|stopping|stopped|unknown).
- ``--session-id`` — Session identifier.
- ``--transport`` — Session transport hint.
- ``--daemon-pid`` — Daemon process id.
- ``--metadata`` — Inline JSON metadata object.
- ``--metadata-file`` — Path to JSON metadata file.
- ``--force`` — Replace participant if it already exists. (default: False)
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:participants-update checksum=bdbbfd3f44d5 -->
#### `participants-update`
participants-update function for thread
**Policy:** `01-thread-01-runtime`, `02-task-03-change-tracking`
**Selectors:** `process`, `thread`
**Flags:**
- ``--runtime-root`` — Override runtime root.
- ``--process`` — Process slug.
- ``--thread`` — Thread slug.
- ``--participant-id`` — Participant identifier. [required]
**Hooks:** _None_
<!-- END CLI -->

<!-- BEGIN CLI: function=thread:participants-list checksum=c8768bfb0393 -->
#### `participants-list`
participants-list function for thread
**Policy:** `01-thread-01-runtime`
**Selectors:** `process`, `thread`
**Flags:**
- ``--runtime-root`` — Override runtime root.
- ``--process`` — Process slug.
- ``--thread`` — Thread slug.
- ``--type`` — Filter participants by type.
- ``--status`` — Filter participants by status.
- ``--participant-id`` — Filter by participant identifier.
- ``--json`` — Return raw manifest JSON instead of structured payload. (default: False)
**Hooks:** _None_
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
