---
title: "Rule 02 Task Lifecycle"
status: "template"
author:
  agent: desktop-manager
  process: cli-rules
  thread: agent-cli-rules
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
3. Follow the ADI loop (analysis → design → implementation change) using the object-call helpers in the table above.
4. Capture receipts from every CLI call; reference them in backlog/overview updates and ensure the thread desktop reflects the latest changes.
5. Notify the bound thread (and Control Center desktop) when receipts land so the human/agent pair sees the evolution immediately.

## 2. Lifecycle Phases

### 2.1 Analysis
- **When**: start every task by writing analysis before any design or implementation work.
- **What**: document the current state—problem statement, dependencies, references, and knowledge gaps.
- **How**: `aware-cli object call --type task --id <project>/<task> --function analysis --content ...`.

<!-- BEGIN CLI: function=task:analysis -->
<!-- END CLI -->

### 2.2 Design
- **When**: begin design once analysis establishes scope.
- **What**: describe the intended future state—contracts, global impact, repository touch points—and link back to analysis doc IDs before implementation.
- **How**: `aware-cli object call --type task --id <project>/<task> --function design --version-bump minor|patch`.

<!-- BEGIN CLI: function=task:design -->
<!-- END CLI -->

### 2.3 Implementation & Change Tracking
- **When**: document every implementation milestone or behavioural change.
- **What**: summarise actions, tests, and reference the analysis/design docs that authorised the work.
- **How**: `aware-cli object call --type task --id <project>/<task> --function change --content-file ...`.

<!-- BEGIN CLI: function=task:change -->
<!-- END CLI -->

### 2.4 Overview maintenance
- **When**: update whenever task focus, blockers, or status changes materially.
- **What**: keep the snapshot short; place deeper narrative in analysis/backlog.
- **How**: `aware-cli object call --type task --id <project>/<task> --function overview --content-file ...`.

<!-- BEGIN CLI: function=task:overview -->
<!-- END CLI -->

### 2.5 Backlog
- **When**: append progress entries daily or when notable events occur.
- **What**: concise bullets describing actions, decisions, receipts; never edit historical entries.
- **How**: `aware-cli object call --type task --id <project>/<task> --function backlog --content ...`.

<!-- BEGIN CLI: function=task:backlog -->
<!-- END CLI -->

### 2.6 Lifecycle Administration
#### Task Creation
- Run `aware-cli object call --type project --id <project> --function create-task --task <slug>` to scaffold a new task. By default the task is RUNNING and created under `tasks/<slug>/`.
- Use `--queued` (or `--status queued`) when you need the task staged in `tasks/_pending/`. Add `--backlog-entry` to log creation and `--no-index-refresh` for batch runs; otherwise the project task index refreshes automatically.

<!-- BEGIN CLI: function=project:create-task -->
<!-- END CLI -->

#### Status Updates
- Move tasks between `_pending/`, root, and `_completed/` with `aware-cli object call --type task --id <project>/<task> --function update-status --status <queued|running|finished-succeeded|finished-failed>`.
- Supply `--reason` to update OVERVIEW/backlog with traceable notes; omit `--no-index-refresh` to keep `.index.json` aligned.

<!-- BEGIN CLI: function=task:update-status -->
<!-- END CLI -->

### 2.7 Project Index Maintenance
- **When**: only after out-of-band edits leave task metadata inconsistent.
- **What**: rebuild `.index.json` so CLI/Studio can resolve task slugs.
- **How**: `aware-cli object call --type project --id <project> --function task-index-refresh [--all]`.

<!-- BEGIN CLI: function=project:task-index-refresh -->
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
