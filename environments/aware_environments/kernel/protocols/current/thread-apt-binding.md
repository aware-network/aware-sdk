---
id: "protocol-thread-apt-binding"
slug: "thread-apt-binding"
title: "Thread-APT Binding Protocol"
version: "0.1"
summary: "Bind APT to Thread runtime as participant for coordination visibility."
targets:
  - object: thread
    functions:
      - add-participant
      - list-participants
  - object: agent
    functions:
      - whoami
depends_on:
  - apt-bootstrap
---

# Thread-APT Binding Protocol

## When to Use

**After APT Bootstrap OR when APT exists but not bound to Thread:**
- APT identity established (agent/process/thread scaffold)
- Need Thread runtime for coordination
- Work must be visible in Studio (Desktop cards)
- Case 3 (unknown): Extends apt-bootstrap
- Case 2 (partially known): Session match but no Thread binding

## Philosophy

**Super Intelligence = Context Resolution**

Agent figures out WHERE to bind, WHAT context to use—without requiring human to understand OS internals. This is a FEATURE: AI makes Aware accessible to everyone.

## Decision Tree

### Phase 1: Thread Discovery

**Investigate existing threads under process:**

```bash
aware-cli object list --type thread --process <process-slug>
```

**Evaluate relevance:**
- What work am I doing? (task analysis, conversation, etc.)
- Which thread context matches?
- Is work already happening on a thread?

**Decision:**
- **SELECT** if existing thread relevant
- **CREATE** if no relevant thread found

### Phase 2: Thread Selection/Creation

**If SELECT (thread exists):**
- Thread already has context (bound objects, participants)
- Join as participant (Phase 3)

**If CREATE (no relevant thread):**

```bash
# Create thread runtime under process
aware-cli object call --type thread --function create \
  --process <process-slug> \
  --thread <thread-slug> \
  --title "Thread title" \
  --description "Context description"
```

**Generates:**
- Thread runtime at `docs/runtime/process/<process>/threads/<thread>/`
- `thread.json` (metadata)
- `participants.json` (empty, ready for participants)
- `branches/` directory (OIG state)
- `pane_manifests/` directory (bound OPGs)

### Phase 3: Participant Registration

**Bind APT as Thread participant:**

```bash
aware-cli object call --type thread --id <thread-slug> \
  --function add-participant \
  --actor-id <actor-id> \
  --actor-kind agent \
  --apt-path <agent/process/thread>
```

**Updates:**
- `participants.json` with Actor entry:
  ```json
  {
    "actor_id": "aa1d6d0c-1155-421b-a658-01e0572821d9",
    "actor_kind": "agent",
    "actor_slug": "desktop-manager/studio-materialization/identity-terminal-foundation",
    "apt_path": "docs/identities/agents/desktop-manager/.../",
    "joined_at": "2025-10-31T18:50:00Z",
    "roles": ["memory-baseline", "project-task-baseline"]
  }
  ```

**Result:**
- APT is Thread participant
- Work now visible in Studio
- Receipts flow through Thread
- Desktop cards update with commits

## Verification

**Confirm binding:**

```bash
# List thread participants
aware-cli object call --type thread --id <thread-slug> \
  --function list-participants

# Verify APT sees Thread
AWARE_THREAD=<thread-slug> \
aware-cli object call --type agent --id <agent> --function whoami
```

**Expected:**
- Participants list includes APT actor_id
- whoami shows Thread binding (no mismatch warnings)

## Outcomes

After successful binding:
- ✅ APT bound to Thread runtime
- ✅ Thread.participants.json includes Actor
- ✅ Work flows through Thread → Studio visibility
- ✅ Receipts enriched with thread_id
- ✅ No orphan work (everything at Thread level)

## Auto-Binding (Kernel Extension - Future)

**When OPG root created (Task, Conversation):**
- Kernel detects object creation
- If no Thread context → error OR auto-bind to Thread
- Creates branch in `branches/`
- Adds to `pane_manifests/`

**Example:**
```
Agent creates Task → kernel runtime extension
  → thread.bind_object(task_id, opg_type="TaskOPG")
    → branches/task/<task-slug>.json
    → pane_manifests/task updated
```

## Integration with APT Bootstrap

**APT Bootstrap (apt-bootstrap protocol) ends with:**
- APT identity established
- AGENT.md generated
- Actor ID assigned
- **Missing:** Thread binding

**Thread-APT Binding continues:**
- Discover/select/create Thread
- Add APT as participant
- Now ready for work

**Combined Flow (Case 3 - Unknown):**
```
1. APT Bootstrap → Identity
2. Thread-APT Binding → Context
3. Work → Receipts visible in Studio
```

## Super Intelligence Pattern

**AI resolves context autonomously:**
1. "I need identity" → apt-bootstrap (agent/process/thread)
2. "I need coordination surface" → thread-apt-binding (participant)
3. "I create object" → kernel auto-binds to Thread
4. "I work" → receipts flow, Studio sees everything

**Result:** User doesn't need to understand agents, threads, or protocols. AI figures it out.

## Supporting Rules

- **Rule 01 · Agent Identity** — create-process/create-thread/whoami
- **Rule 06 · Thread Binding** (this protocol operationalizes it)

## Example: Full Case 3 Bootstrap + Binding

```bash
# 1. APT Bootstrap (completed)
aware-cli object call --type agent --id desktop-manager \
  --function create-thread \
  --process studio-materialization \
  --thread identity-terminal-foundation

# 2. Thread Discovery
aware-cli object list --type thread --process studio-materialization

# 3. Thread Selection (or create if none relevant)
# Assume selecting existing thread: "interface-orchestration"

# 4. Participant Registration
aware-cli object call --type thread --id interface-orchestration \
  --function add-participant \
  --actor-id aa1d6d0c-1155-421b-a658-01e0572821d9 \
  --actor-kind agent \
  --apt-path desktop-manager/studio-materialization/identity-terminal-foundation

# 5. Verify
aware-cli object call --type thread --id interface-orchestration \
  --function list-participants
```

---

**Next:** Implement add-participant function, participants.json schema, kernel auto-binding hooks
