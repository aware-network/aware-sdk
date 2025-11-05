---
title: "Thread · Object · Agent Overview"
created: "2025-10-31 00:25:29"
updated: "2025-10-31 00:25:29"
author: "Codex / main.thread-object-agent"
---

# AWARE Kernel · Thread → Object → Agent

## Purpose
- Establish a shared vocabulary for how the kernel binds threads, objects, and agents.
- Bridge the textual rule set to the studio experience (panels, providers, receipts).
- Provide a launch point for new rulebook work under `kernel/rules/`.

## Core Definitions
- **Thread** · coordination surface that binds humans, agents, terminals, and bound objects for a session.
- **Object** · kernel-registered resource that exposes public async methods and emits state diffs via receipts.
- **Agent** · execution engine (human-in-the-loop or LLM-backed) that invokes object methods through the adapters.

## Experience Map
- **Human Panel (top)** · declares who is observing/steering; sourced from thread participants and receipts.
- **Agent Panel (bottom)** · shows active agent identity, roles, and current LLM/provider selection.
- **Terminal (right)** · renders the provider-specific interaction surface while remaining receipt-aware.
- **Desktop Cards (center)** · task and conversation panes rendered as cards; each subscribes to thread receipts.

## Flow 1 · Thread → Object → Agent
1. Human or automation selects a thread (e.g., `aware-manager/main/thread-object-agent`).
2. Thread manifest binds required objects (task, conversation, repository) and ensures policy alignment.
3. Kernel adapters expose object methods through the CLI and studio.
4. Agents execute plans against those objects, recording every mutation as a receipt.

**Outcome:** the thread always knows which objects are queued for execution and which agent identity is responsible for upcoming work.

## Flow 2 · Agent → Object → Thread
1. Agent (LLM or human) chooses a provider in the agent panel and opens a terminal session.
2. The agent issues object calls (via CLI or studio actions) against the kernel registry.
3. Each call returns a **receipt** that captures the object, operation, selectors, and file-system diff.
4. The thread ingests receipts, refreshes bound cards, and notifies the human panel of state changes.

**Outcome:** receipts form the shared ledger—agents act, objects record, threads broadcast.

## Receipt Loop Responsibilities
- **Environment** · validates planned operations, emits receipts, and reports deltas to watchers.
- **CLI** · surfaces permissible actions, executes calls, and forwards receipts to the studio.
- **Studio** · displays receipts, updates desktop cards, and highlights task/conversation evolution.

## Human ↔ Agent Collaboration Checklist
- Maintain working memory freshness for every active thread (≤30 minutes during sessions).
- Store episodic summaries after significant receipt batches.
- Announce provider switches so humans can correlate LLM decisions with receipts.
- Escalate when thread manifests or receipts fall out of sync with observed file changes.

## Roadmap Highlights
- Extend this README with concrete provider manifests once human/agent panels are live in the studio.
- Publish the detailed rulebook (`kernel/rules/thread-object-agent-rulebook.md`) describing lifecycle invariants.
- Wire Delta Watcher outputs so task and conversation cards emit contextual summaries automatically.

> Threads select the work, objects enforce the rules, agents perform the changes—receipts keep everyone aligned.


