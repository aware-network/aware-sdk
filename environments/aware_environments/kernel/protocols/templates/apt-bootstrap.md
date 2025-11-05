---
id: "protocol-apt-bootstrap"
slug: "apt-bootstrap"
title: "APT Bootstrap Protocol"
version: "0.2"
summary: "Guidance for establishing Agent Process Thread identity when starting without APT context."
targets:
  - object: agent
    functions:
      - create-process
      - create-thread
      - whoami
---

# APT Bootstrap Protocol

## When to Use

- Agent session starts without APT binding
- No `AWARE_AGENT`/`PROCESS`/`THREAD` environment variables
- No terminal descriptor with APT context
- Unknown which agent/process/thread to bind

## Decision Tree

### Phase 1: Agent Discovery

**Investigate first** - List all agents and evaluate domain fit:

```bash
aware-cli object list --type agent
```

**Evaluate:** Which agent's domain matches your work?
- Studio/Interface → `desktop-manager`
- CLI/Tooling → `aware-manager`
- Infrastructure → `aware-infra-worker`

**Decision:**
- **REUSE** if work fits existing agent domain
- **CREATE** if new personality needed (rare, justify)

### Phase 2: Process Resolution

**Check existing processes** under selected agent (from list output).

**Evaluate:** Does existing process cover this capability?

**Decision:**
- **REUSE** if capability already scoped
- **CREATE** if new long-running capability needed

```bash
# Create process under agent
aware-cli object call --type agent --id <agent-slug> \
  --function create-process --process <process-slug>
```

### Phase 3: Thread Creation

**Always CREATE** - Threads are session-specific.

```bash
# Create thread under process
aware-cli object call --type agent --id <agent-slug> \
  --function create-thread \
  --process <process-slug> \
  --thread <thread-slug> \
  --description "Session focus description"
```

**Generates:**
- Thread scaffold with roles
- AGENT.md constitutional guide
- Actor ID for receipt attribution
- 5 receipts (registry, roles, AGENT.md, apt.json, actor registry)

### Phase 4: Verification

**Confirm bindings** with environment variables:

```bash
AWARE_AGENT=<agent-slug> \
AWARE_PROCESS=<process-slug> \
AWARE_THREAD=<thread-slug> \
aware-cli object call --type agent --id <agent-slug> --function whoami
```

**Verify:**
- ✅ APT bindings correct
- ✅ AGENT.md generated (check path in output)
- ✅ Receipts captured
- ⚠️ Terminal mismatch warnings expected (resolved in Rule 06)

## Default Fallback

When no suitable agent exists AND auto-creation triggered:
- Agent: `unknown` or provider-specific (e.g., `claude-code`)
- Process: `main`
- Thread: `main`

Result: `unknown/main/main`

## Human Acceptance

Before CREATE operations:
- Present discovery results to human
- Show recommended agent/process/thread
- Wait for approval or selection adjustment
- CLI may prompt, Studio shows identity selection panel

## Outcomes

After successful bootstrap:
- ✅ APT identity established
- ✅ AGENT.md generated with roles/rules
- ✅ Actor ID assigned for receipts
- ✅ Audit trail via receipts
- ❌ Thread runtime binding (see Rule 06 - next step)

## Supporting Rules

- **Rule 01 · Agent Identity** — create-process/create-thread/whoami functions
- **Rule 06 · Thread Binding** (pending) — bind APT scaffold to Thread runtime with object manifests

## Example: Full Bootstrap Session

```bash
# 1. Discovery
aware-cli object list --type agent | grep desktop-manager

# 2. Create process (if new capability)
aware-cli object call --type agent --id desktop-manager \
  --function create-process --process studio-materialization

# 3. Create thread (always)
aware-cli object call --type agent --id desktop-manager \
  --function create-thread \
  --process studio-materialization \
  --thread identity-terminal-foundation \
  --description "FS-first Identity Pane and Terminal integration"

# 4. Verify
AWARE_AGENT=desktop-manager \
AWARE_PROCESS=studio-materialization \
AWARE_THREAD=identity-terminal-foundation \
aware-cli object call --type agent --id desktop-manager --function whoami
```
