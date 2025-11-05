---
title: "Rule 00 Environment Constitution"
status: template
author:
  agent: desktop-manager
  process: cli-rules
  thread: agent-cli-rules
---

# Rule 00 · Environment Constitution

## 1  Mission
1. Establish a single definition of thread/object/agent that every environment consumer follows.
2. Describe how thread/object/agent interactions surface in studio panels and provider terminals.
3. Make receipts the authoritative record for every mutation.

---

## 2  Thread/Object/Agent Model
1. **Thread** · Object-agnostic execution surface. It binds humans, agents, providers, and selected objects, never mutates state, and orchestrates focus/notifications.
2. **Object** · Environment-defined contract exposing functions → state change → receipt. The kernel environment publishes the shared “Aware OS” ontology (thread, agent, etc.); domains may add objects but MUST honour the function→state→receipt invariant.
3. **Agent** · AI execution persona (never human) operating under the agent_process_thread model. Agents attach to threads, invoke object functions, and own the receipts they generate.

**Invariant (must hold):** Threads do not mutate state. Agents do not bypass object methods. Objects do not skip receipt generation.

---

## 3  Bidirectional Flow

### 3.1 Thread → Object → Agent
| Step | Responsibility | Receipt Trigger |
| --- | --- | --- |
| Select thread | Human picks thread; CLI confirms manifest | `thread.session.update` |
| Bind objects | Thread manifest lists task/conversation/repository bindings | `thread.branch.set` |
| Advertise methods | Environment adapter handlers expose object functions | N/A |
| Delegate execution | Agent assumes responsibility for listed objects | On method call |

### 3.2 Agent → Object → Thread
| Step | Responsibility | Receipt Trigger |
| --- | --- | --- |
| Choose provider | Agent panel selects LLM/provider | `agent.session.update` |
| Execute object method | CLI/Studio invokes environment handler | `object.write_plan` |
| Emit receipt | Environment validates diff, writes receipt | `environment.receipt` |
| Refresh thread | Desktop updates cards & notifications | `thread.delta` |

---

## 4  Receipts as Ledger
1. Every object write plan MUST emit a receipt before any filesystem mutation.
2. Receipts MUST capture: object identifier, thread identifier, selectors, operation (`create`/`update`/`delete`), diff summary (including changed files and `fs_ops[]`), author/apt_id, timestamps, and state hashes (`pre_hash`/`post_hash`).
3. CLI MUST forward receipt identifiers to Studio panels; Delta (thread feed) mirrors them to cards/feed.
4. Agents MUST reference receipt IDs in working/episodic memory; humans trigger actions via Studio and interpret receipts through the thread feed.

---

## 5  Experience Layout Guidelines
1. **Three-window layout (single workspace):**
   - **Left · Orchestration** — Environment/process/thread selectors; confirms bindings and active participants.
   - **Center · Desktop** — Data panes rendered as cards (tasks, code, conversations). Human/agent overlays appear here to share identity context.
   - **Right · Execution** — Provider terminal (agent run surface) plus auxiliary interaction objects (e.g., conversations).
2. **Provider Switch:** every provider change MUST emit an `agent.session.update` receipt (provider + session_id).
3. **Cards:** task/conversation cards subscribe to thread receipts and render inline diff summaries.
4. **Thread Feed:** left timeline shows latest receipts grouped by thread.

---

## 6  Operational Responsibilities (Layered)
- **Environment layer:** enforce write-plan validation, emit receipts, maintain registry metadata.
- **CLI layer:** provide object-first interfaces (`object list/resolve/call`), enforce rule constraints, stream receipts to callers.
- **Human layer (Studio):** select threads/objects, trigger pane → object → function calls via the UI (environment executes), interpret receipts, coordinate with agents.
- **Agent layer (Rule 01):** execute via agent_process_thread → pane → object → function calls, update working memory ≤30 minutes, append episodic entries after notable receipt batches, cite receipt IDs in responses.

---

## 7  Object-First CLI Overview
1. **List objects** with `aware-cli object list --type <object>` to discover available capabilities.
2. **Resolve canonical IDs** using `aware-cli object resolve --type <object> --value <slug-or-uuid>` before mutating state.
3. **Call functions** through `aware-cli object call --type <object> --id <canonical-id> --function <name> [-- ...]`, providing selectors after `--` when needed.
4. **Capture receipts** from every invocation and reference them in working memory, backlog entries, or project documentation.
5. **Regenerate the constitution guide** with environment render commands (e.g., `aware-cli object call --type environment --function render-agent --write ...`) whenever roles or rules change so onboarding docs stay aligned.

---

## 8  Further Reading
- [Rule 01 · Agent Identity](../current/01-agent.md) — identity scaffolds and agent process/thread management.
- [Rule 02 · Task Lifecycle](../current/02-task.md) — project coordination and ADI workflow.
- [Object-first CLI overview](../../../../../tools/cli/docs/USAGE.md#object-first-cli-overview) — discover/list/resolve/call patterns, receipt handling, and guide regeneration.