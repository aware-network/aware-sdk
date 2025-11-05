---
title: Rule 02 Task Lifecycle
status: template
author:
  agent: desktop-manager
  process: cli-rules
  thread: agent-cli-rules
aware_cli_version: 0.8.3
generated_at: '2025-10-25T04:30:18.346450Z'
source_template: templates/02-task.md
---

# Rule 02 · Task Lifecycle

## 1. Overview Table
| Artifact | Purpose | CLI command | Policy |
| --- | --- | --- | --- |
| OVERVIEW.md | Current status, focus, blockers | `aware-cli object call --type task --id <project>/<task> --function overview` | `modifiable`
| backlog/YYYY-MM-DD.md | Daily execution log | `aware-cli object call --type task --id <project>/<task> --function backlog` | `append_entry`
| analysis/<timestamp>.md | Problem understanding before design | `aware-cli object call --type task --id <project>/<task> --function analysis` | `append_entry`
| design/<timestamp>.md | Implementation plan plus version bump | `aware-cli object call --type task --id <project>/<task> --function design --version-bump minor|patch` | `append_entry` + `version_bumper`
| implementation/changes/<timestamp>.md | Executed work, tests, linked analysis/design IDs | `aware-cli object call --type task --id <project>/<task> --function change` | `append_entry`
| tasks/<slug>/ | Scaffold new task lifecycle structure (default RUNNING) | `aware-cli object call --type project --function create-task --task <slug>` | `object`
| Lifecycle status (queued → running → finished) | Move directories + sync metadata | `aware-cli object call --type task --function update-status --status <state>` | `object`

## 1.1 Project Coordination Flow
1. Review the project summary (`PROJECT/OVERVIEW.md`) to confirm scope, status, and linked tasks.
2. Create or resolve the active task via `aware-cli object call --type project --function create-task`.
3. Follow the ADI loop (analysis → design → implementation change) using the object-call helpers above.
4. Capture receipts from every CLI call; reference them in backlog/overview updates and ensure the thread desktop reflects the latest changes.
5. Notify the bound thread (and Control Center desktop) when receipts land so the human/agent pair sees the evolution immediately.

## 2. Lifecycle Phases

### 2.1 Analysis
- **When**: start every task by writing analysis before any design or implementation work.
- **What**: document the current state—problem statement, dependencies, references, and knowledge gaps.
- **How**: `aware-cli object call --type task --id <project>/<task> --function analysis --content ...`.

<!-- BEGIN CLI: function=task:analysis checksum=72faa5e602fd -->
#### `analysis`
Create a timestamped analysis note (append-only).
**Policy:** `02-task-01-lifecycle`
**Selectors:** `project`, `task`
**Flags:**
- `--title` — Frontmatter title; defaults to derived slug.
- `--slug` — Override slug used in filename (timestamp prefix preserved).
- `--summary` — Optional summary text inserted into the template body or backlog entry.
- `--content` — Markdown body supplied inline.
- `--content-file PATH` — Read Markdown body from the given file.
- `--open [editor]` — Open the created file in $EDITOR or provided command.
- `--dry-run` — Preview file contents without writing to disk.
- `--force` — Allow overwriting existing append-only docs (use sparingly).
**Hooks:** _None_
**Examples:**
```bash
aware-cli object call --type task --projects-root docs/projects --id my-project/sample-task --function analysis --title "Investigate auth" --content '# Findings'
```
<!-- END CLI -->

### 2.2 Design
- **When**: begin design once analysis establishes scope.
- **What**: describe the intended future state—contracts, global impact, repository touch points—and link back to analysis doc IDs before implementation.
- **How**: `aware-cli object call --type task --id <project>/<task> --function design --version-bump minor|patch`.

<!-- BEGIN CLI: function=task:design checksum=526c613c9758 -->
#### `design`
Draft or update a design iteration with semantic version scaffolding.
**Policy:** `02-task-01-lifecycle`
**Selectors:** `project`, `task`
**Flags:**
- `--title` — Frontmatter title; defaults to derived slug.
- `--slug` — Override slug used in filename (timestamp prefix preserved).
- `--summary` — Optional summary text inserted into the template body or backlog entry.
- `--content` — Markdown body supplied inline.
- `--content-file PATH` — Read Markdown body from the given file.
- `--open [editor]` — Open the created file in $EDITOR or provided command.
- `--dry-run` — Preview file contents without writing to disk.
- `--force` — Allow overwriting existing append-only docs (use sparingly).
- `--version-bump {major|minor|patch|none}` — Seed version in template (defaults to 1.0.0).
**Hooks:** `version_bumper`
**Examples:**
```bash
aware-cli object call --type task --projects-root docs/projects --id my-project/sample-task --function design --title "API error handling" --version-bump minor --content-file design.md
```
<!-- END CLI -->

### 2.3 Implementation & Change Tracking
- **When**: document every implementation milestone or behavioural change.
- **What**: summarise actions, tests, and reference the analysis/design docs that authorised the work.
- **How**: `aware-cli object call --type task --id <project>/<task> --function change --content-file ...`.

<!-- BEGIN CLI: function=task:change checksum=0da36bd05a52 -->
#### `change`
Record an implementation change log entry under implementation/changes/.
**Policy:** `02-task-01-lifecycle`
**Selectors:** `project`, `task`
**Flags:**
- `--title` — Frontmatter title; defaults to derived slug.
- `--slug` — Override slug used in filename (timestamp prefix preserved).
- `--summary` — Optional summary text inserted into the template body or backlog entry.
- `--content` — Markdown body supplied inline.
- `--content-file PATH` — Read Markdown body from the given file.
- `--open [editor]` — Open the created file in $EDITOR or provided command.
- `--dry-run` — Preview file contents without writing to disk.
- `--force` — Allow overwriting existing append-only docs (use sparingly).
**Hooks:** _None_
**Examples:**
```bash
aware-cli object call --type task --projects-root docs/projects --id my-project/sample-task --function change --title "Implement change helper" --content '* Added docs generation'
```
<!-- END CLI -->

### 2.4 Overview maintenance
- **When**: update whenever task focus, blockers, or status changes materially.
- **What**: keep the snapshot short; place deeper narrative in analysis/backlog.
- **How**: `aware-cli object call --type task --id <project>/<task> --function overview --content-file ...`.

<!-- BEGIN CLI: function=task:overview checksum=204da904c688 -->
#### `overview`
Append a note to the task OVERVIEW.md (modifiable document).
**Policy:** `02-task-01-lifecycle`
**Selectors:** `project`, `task`
**Flags:**
- `--title` — Frontmatter title; defaults to derived slug.
- `--slug` — Override slug used in filename (timestamp prefix preserved).
- `--summary` — Optional summary text inserted into the template body or backlog entry.
- `--content` — Markdown body supplied inline.
- `--content-file PATH` — Read Markdown body from the given file.
- `--open [editor]` — Open the created file in $EDITOR or provided command.
- `--dry-run` — Preview file contents without writing to disk.
- `--force` — Allow overwriting existing append-only docs (use sparingly).
**Hooks:** _None_
**Examples:**
```bash
aware-cli object call --type task --projects-root docs/projects --id my-project/sample-task --function overview --title "Task Overview" --content "## Status
- Synced README with CLI"
```
<!-- END CLI -->

### 2.5 Backlog
- **When**: append progress entries daily or when notable events occur.
- **What**: concise bullets describing actions, decisions, receipts; never edit historical entries.
- **How**: `aware-cli object call --type task --id <project>/<task> --function backlog --content ...`.

<!-- BEGIN CLI: function=task:backlog checksum=0efea0bd3013 -->
#### `backlog`
Append a backlog entry for the given task (grouped by date).
**Policy:** `02-task-01-lifecycle`
**Selectors:** `project`, `task`
**Flags:**
- `--title` — Frontmatter title; defaults to derived slug.
- `--slug` — Override slug used in filename (timestamp prefix preserved).
- `--summary` — Optional summary text inserted into the template body or backlog entry.
- `--content` — Markdown body supplied inline.
- `--content-file PATH` — Read Markdown body from the given file.
- `--open [editor]` — Open the created file in $EDITOR or provided command.
- `--dry-run` — Preview file contents without writing to disk.
- `--force` — Allow overwriting existing append-only docs (use sparingly).
**Hooks:** _None_
**Examples:**
```bash
aware-cli object call --type task --projects-root docs/projects --id my-project/sample-task --function backlog --title "Daily Notes" --content "- Investigate CLI docs"
```
<!-- END CLI -->

### 2.6 Project Index Maintenance
- **When**: only after out-of-band edits leave task metadata inconsistent.
- **What**: rebuild `.index.json` so CLI/Studio can resolve task slugs.
- **How**: `aware-cli object call --type project --id <project> --function task-index-refresh [--all]`.

<!-- BEGIN CLI: function=project:task-index-refresh checksum=049a4136fd38 -->
#### `task-index-refresh`
Regenerate docs/projects/<project>/tasks/.index.json (use --all to rebuild every project).
**Policy:** `02-task-01-lifecycle`, `02-task-03-change-tracking`
**Selectors:** _None_
**Flags:**
- `--all` — Process every project under the root.
**Hooks:** _None_
<!-- END CLI -->

## 3. Operational Checklist
- Initialise OVERVIEW.md.
- Capture baseline analysis before design.
- Draft design and record version bump.
- Document changes as work completes.
- Append backlog notes (automatically timestamped).
- Optionally sync coordination history.
- Close out task: final overview update + backlog entry, record apply receipts.

## 4. Validation Hooks
- Copy CLI apply receipts into backlog or working memory.
- Run targeted renderer checks if fragments appear stale.
- Execute CLI test suite after structural edits.
- Capture coordination updates via `aware-cli updates --since` when relevant.

## 5. Testing / APT Validation Plan
- Run dedicated APT using this template; log observations.

## 6. Appendices
- Reference Rule 04 (memory) and Rule 05 (process/thread).
- Note pending CLI features.
