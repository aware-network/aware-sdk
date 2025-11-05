---
id: "environment-protocol"
layer: "environment"
mandatory: true
version: "1.0.0"
updated: "2025-11-04"
summary: "Protocols as executable runtime guides with three-tier command grammar (exec/required/suggested) for AI-native context resolution"
---

# Environment Protocol Framework
### _"Skills with runtime state: guidance + live data = autonomous AI context resolution"_

## Purpose
This document defines the Protocol framework for AWARE environments. Protocols are executable guides that combine procedural guidance with live runtime data, transforming static templates into dynamic context providers. They represent the next generation of AI agent guidance systems, moving beyond static examples to real-time state injection.

---

## 1. What is a Protocol?

A **Protocol** is an environment-defined executable guide that:

1. **Provides procedural guidance** through decision trees and step-by-step instructions
2. **Executes CLI commands** to inject live runtime state into the guidance
3. **Resolves execution context** autonomously for AI agents
4. **Maintains single source of truth** by using actual CLI commands (no duplication)

### Core Characteristics

| Property | Description |
|----------|-------------|
| **Template-based** | Stored as markdown files with embedded CLI commands |
| **Runtime-executed** | Commands execute when protocol is rendered |
| **Environment-scoped** | Each environment declares its own protocols |
| **Thread-linked** | Protocols activate when agents join threads (future) |
| **State-injected** | Live data replaces static examples |

### Why Protocols?

**Problem**: Static documentation forces AI agents to manually discover runtime context, leading to:
- Repetitive command execution by every agent
- Outdated examples in documentation
- Semantic duplication between docs and CLI implementations
- No systematic way to resolve "where should I work?"

**Solution**: Protocols encapsulate runtime discovery patterns and execute them on-demand, providing fresh context every time.

---

## 2. Protocols vs Claude-Code Skills

Protocols are inspired by claude-code skills but extend them with runtime state injection and environment integration.

### Comparison Table

| Aspect | Claude-Code Skills | AWARE Protocols |
|--------|-------------------|-----------------|
| **Guidance** | ✅ Step-by-step instructions | ✅ Decision trees + phases |
| **Examples** | ❌ Static code examples | ✅ Live CLI execution results |
| **State** | ❌ Hardcoded sample data | ✅ Real-time system state |
| **SSOT** | ❌ Duplicates actual commands | ✅ Uses canonical CLI layer |
| **Runtime** | ❌ Agent manually replicates | ✅ Environment auto-executes |
| **Context** | ❌ Agent must discover scope | ✅ Protocol resolves scope |
| **Versioning** | ❌ Examples drift from reality | ✅ Commands auto-migrate |
| **Extensibility** | ❌ IDE-specific | ✅ Environment-extensible |

### Example: Thread Discovery

**Claude-Code Skill (Static)**:
```markdown
## Step 1: List threads

Run this command:
```bash
aware-cli object list --type thread
```

You should see something like:
```json
[
  {"id": "abc123", "slug": "kernel/boot"},
  {"id": "def456", "slug": "studio/ui"}
]
```
```

**AWARE Protocol (Dynamic)**:
```markdown
## Phase 1: Thread Discovery

Discover available threads:
```
object list --type thread
```

Evaluate which thread matches your work scope.
```

When rendered, the protocol executes `object list --type thread` and injects actual current threads:

```markdown
## Phase 1: Thread Discovery

Discover available threads:
```
object list --type thread
```

Output:
```
[
  {"id": "abc123", "slug": "kernel/boot", "active": true},
  {"id": "def456", "slug": "studio/ui", "active": false}
]
```

Evaluate which thread matches your work scope.
```

---

## 3. CLI Command Embedding

Protocols use **code blocks without language tags** to denote CLI commands that should be executed at render time.

### Syntax Rules

1. **No language tag**: Code blocks without language identifiers are CLI commands
2. **Exact CLI syntax**: Use actual command syntax minus the `aware-cli` prefix
3. **No `aware-cli` prefix**: Commands are executed through the CLI engine directly
4. **Command mode markers**: HTML comments specify execution behavior (exec/required/suggested)

### Command Grammar: Three-Tier System

Protocols distinguish between three types of commands using HTML comment markers:

#### `<!-- command:exec -->` - Auto-execute, inject state

**Purpose**: Provide live runtime context to AI
**Behavior**: Command executes during protocol rendering, results injected into output
**Use cases**: Read files, run linters, list available objects, query current state

```markdown
<!-- command:exec -->
```
object list --type thread
```
```

#### `<!-- command:required -->` - AI must execute

**Purpose**: Define mandatory actions AI must complete
**Behavior Today**: Command preserved as prose (shows what AI needs to do)
**Behavior Tomorrow**: Thread runtime validates AI executed via receipts, blocks workflow if missing
**Use cases**: Fix code, create commits, update documentation, apply changes

```markdown
<!-- command:required -->
```
code write --path sample.py --content <fixed-code>
```
```

#### `<!-- command:suggested -->` - AI can execute (optional)

**Purpose**: Guide AI towards best practices using broader knowledge
**Behavior Today**: Command preserved as prose
**Behavior Tomorrow**: Thread runtime tracks if executed, provides feedback/metrics
**Use cases**: Re-run tests, verify assumptions, format code, check edge cases

```markdown
<!-- command:suggested -->
```
code format --path sample.py
```
```

#### Default Behavior

Code blocks without mode markers default to `exec` for backward compatibility:

```markdown
```
object list --type thread
```
```

Equivalent to:

```markdown
<!-- command:exec -->
```
object list --type thread
```
```

### Complete Example: Lint-Fixer Protocol

This example demonstrates all three command modes working together:

**Template**:
```markdown
# Lint Fixer Protocol

## Step 1: Read Code (Context)

<!-- command:exec -->
```
code read --path sample.py
```

Analyze the code structure above.

## Step 2: Check Errors (Context)

<!-- command:exec -->
```
code lint --path sample.py
```

Review lint errors. Common issues: unused imports, formatting, type annotations.

## Step 3: Fix Issues (Required)

Based on the actual errors shown above, apply fixes.

<!-- command:required -->
```
code write --path sample.py --content <fixed-code>
```

Replace `<fixed-code>` with corrected implementation addressing all lint errors.

## Step 4: Verify Fix (Suggested)

<!-- command:suggested -->
```
code lint --path sample.py
```

Re-run linter to confirm all issues resolved.

## Step 5: Format Code (Suggested)

<!-- command:suggested -->
```
code format --path sample.py
```

Optional: Apply standard formatting for consistency.
```

**Rendered (Steps 1-2 executed, Steps 3-5 preserved)**:
```markdown
# Lint Fixer Protocol

## Step 1: Read Code (Context)

<!-- command:exec -->
```
code read --path sample.py
```

Output:
```
"""Sample Python file."""

import os  # unused import

def greet( name ):  # spacing issue
    print("Hello, " + name)
```

Analyze the code structure above.

## Step 2: Check Errors (Context)

<!-- command:exec -->
```
code lint --path sample.py
```

Output:
```
[
  {"line": 3, "column": 1, "message": "unused import 'os'"},
  {"line": 5, "column": 11, "message": "unexpected whitespace after '('"}
]
```

Review lint errors. Common issues: unused imports, formatting, type annotations.

## Step 3: Fix Issues (Required)

Based on the actual errors shown above, apply fixes.

<!-- command:required -->
```
code write --path sample.py --content <fixed-code>
```

Replace `<fixed-code>` with corrected implementation addressing all lint errors.

## Step 4: Verify Fix (Suggested)

<!-- command:suggested -->
```
code lint --path sample.py
```

Re-run linter to confirm all issues resolved.

## Step 5: Format Code (Suggested)

<!-- command:suggested -->
```
code format --path sample.py
```

Optional: Apply standard formatting for consistency.
```

**AI Workflow**:
1. ✅ AI sees live code content (Step 1 - executed)
2. ✅ AI sees actual lint errors (Step 2 - executed)
3. ⏯️ AI MUST fix code (Step 3 - required)
4. 💡 AI can verify if needed (Step 4 - suggested)
5. 💡 AI can format if appropriate (Step 5 - suggested)

### Legacy Command Format

**Template (in protocol file)**:
```markdown
Discover objects:
```
object list --type <object>
```

Check thread status:
```
object call --type thread --id <thread-id> --function status
```
```

**Rendered (after execution)**:
```markdown
Discover objects:
```
object list --type thread
```

Output:
```
[{"id": "...", "slug": "kernel/boot"}]
```

Check thread status:
```
object call --type thread --id kernel/boot --function status
```

Output:
```
{"status": "active", "participants": 2}
```
```

### Why This Syntax?

1. **Single source of truth**: Protocol commands ARE the actual CLI commands
2. **Centralized migration**: CLI changes automatically propagate to protocols
3. **No semantic duplication**: Protocol doesn't reimplement command logic
4. **Agent learning**: Agents learn actual commands, not meta-layer abstractions

---

## 4. Protocol Lifecycle

### 4.1 Registration

Protocols are registered in the environment's protocol registry during initialization.

**File Structure**:
```
environments/aware_environments/<environment>/
└── protocols/
    └── templates/
        ├── bootstrap.md       # Protocol template
        └── coordination.md    # Another protocol
```

**Registration** (automatic on environment load):
```python
from aware_environment.protocol.registry import register_protocol

register_protocol(ProtocolSpec(
    slug="bootstrap",
    environment_slug="kernel",
    path="protocols/templates/bootstrap.md",
    title="Bootstrap Protocol",
    description="Initial agent context resolution"
))
```

### 4.2 Rendering

When an agent requests a protocol, the environment renders it with live command execution.

**Render Flow**:
```
1. Load protocol template from filesystem
   ↓
2. Parse markdown to extract CLI command blocks
   ↓
3. For each command block:
   a. Parse command (e.g., "object list --type thread")
   b. Execute via CLI engine (direct call, no subprocess)
   c. Capture output
   ↓
4. Inject results back into markdown
   ↓
5. Return rendered protocol to agent
```

**Code Pattern**:
```python
from aware_environment.renderer import render_protocol

# Agent requests protocol
protocol_md = render_protocol(
    slug="bootstrap",
    context={"process": "kernel"}
)

# Returns markdown with executed commands and live results
```

### 4.3 Execution Engine

Protocols execute CLI commands through the **direct CLI engine** (not subprocess) for security and performance.

**Execution Flow**:
```python
# Parse command
command = "object list --type thread"
parts = command.split()  # ["object", "list", "--type", "thread"]

# Get object spec from registry
obj_type = parts[0]  # "object"
function_name = parts[1]  # "list"
extra_args = parts[2:]  # ["--type", "thread"]

# Execute via handler
spec = get_object_spec(obj_type)
function_spec = spec.functions[function_name]
handler = function_spec.handler_factory()
result = handler.execute(context)

# Format output
output = json.dumps(result.payload, indent=2)
```

---

## 5. Complete Example: Bootstrap Protocol

The bootstrap protocol demonstrates the full protocol pattern: thread discovery → selection → APT creation.

### Template (Before Rendering)

**File**: `environments/aware_environments/kernel/protocols/templates/bootstrap.md`

```markdown
# Bootstrap Protocol

## Overview
Initial context resolution for agents joining the environment without assigned thread.

## Phase 1: Thread Discovery

Discover available threads in the current process:
```
object list --type thread --filter process={{context.process}}
```

Evaluate each thread's purpose and current participants to determine relevance.

## Phase 2: Thread Selection

Resolve the thread ID for your selected scope:
```
object resolve --type thread --value <selected-slug>
```

Verify thread details:
```
object call --type thread --id <thread-id> --function describe
```

## Phase 3: APT Creation

Create your Agent-Process-Thread (APT) identity bound to the selected thread:
```
object call --type agent-thread --function login -- --thread-id <thread-id>
```

You are now a participant in the thread and can access thread-bound objects.
```

### Rendered (After Execution)

```markdown
# Bootstrap Protocol

## Overview
Initial context resolution for agents joining the environment without assigned thread.

## Phase 1: Thread Discovery

Discover available threads in the current process:
```
object list --type thread --filter process=kernel
```

Output:
```
[
  {
    "id": "thread-001",
    "slug": "kernel/boot",
    "title": "Kernel Boot Thread",
    "status": "active",
    "participants": 1
  },
  {
    "id": "thread-002",
    "slug": "kernel/coordination",
    "title": "Kernel Coordination Thread",
    "status": "active",
    "participants": 3
  }
]
```

Evaluate each thread's purpose and current participants to determine relevance.

## Phase 2: Thread Selection

Resolve the thread ID for your selected scope:
```
object resolve --type thread --value kernel/boot
```

Output:
```
{"id": "thread-001", "slug": "kernel/boot"}
```

Verify thread details:
```
object call --type thread --id thread-001 --function describe
```

Output:
```
{
  "slug": "kernel/boot",
  "process": "kernel",
  "title": "Kernel Boot Thread",
  "protocols": ["bootstrap"],
  "objects": ["agent", "thread", "process"],
  "participants": [
    {"id": "agent-001", "role": "coordinator"}
  ]
}
```

## Phase 3: APT Creation

Create your Agent-Process-Thread (APT) identity bound to the selected thread:
```
object call --type agent-thread --function login -- --thread-id thread-001
```

Output:
```
{
  "apt_id": "apt-new-001",
  "agent_id": "agent-002",
  "thread_id": "thread-001",
  "role": "participant",
  "created_at": "2025-11-03T20:30:00Z"
}
```

You are now a participant in the thread and can access thread-bound objects.
```

### AI-Native Test

**Question**: Can the AI resolve execution context autonomously?

**Before (without protocol runtime)**:
1. AI creates APT identity
2. Asks human "where should I work?"
3. Human specifies thread manually
4. ❌ **FAILS**: Human intervention required

**After (with protocol runtime)**:
1. Boot thread runs bootstrap protocol
2. Protocol shows live thread list with participants
3. AI evaluates relevance (e.g., "coordination has 3 participants, I'll join boot")
4. AI creates APT bound to selected thread
5. ✅ **PASSES**: AI autonomously chose scope

---

## 6. Integration with Threads (Future)

### Thread-Protocol Linkage

Threads will declare which protocols they provide, enabling automatic protocol activation.

**Thread Spec (Future)**:
```python
@dataclass
class ThreadSpec:
    slug: str
    process_slug: str
    protocols: List[str]  # Protocol slugs this thread provides
    objects: List[str]    # Object types accessible in this thread
```

**Example**:
```python
boot_thread = ThreadSpec(
    slug="kernel/boot",
    process_slug="kernel",
    protocols=["bootstrap"],  # Bootstrap protocol available here
    objects=["agent", "thread", "process"]
)
```

### Protocol Activation

When an agent joins a thread:
1. Agent binds to thread via `agent-thread.login`
2. Thread returns list of available protocols
3. Agent can request protocol rendering for guidance
4. Protocol executes with thread context automatically

**Flow**:
```
Agent → join thread → thread provides protocols → agent renders protocol → protocol executes commands in thread context
```

---

## 7. Security Considerations

### Command Injection Prevention

1. **Whitelist only registered objects**: Commands can only target objects registered in environment
2. **No shell execution**: Commands execute through CLI engine, not shell subprocess
3. **Timeout enforcement**: 30-second timeout on all command executions
4. **Sandboxing**: Commands run with same permissions as environment (no escalation)

### Resource Limits

- **Memory**: Monitor protocol rendering to prevent memory exhaustion
- **CPU**: Command timeouts prevent infinite loops
- **Network**: Commands inherit environment's network restrictions

---

## 8. Performance Characteristics

### Expected Performance

| Metric | Target | Notes |
|--------|--------|-------|
| **Protocol render time** | < 100ms | Includes 1-3 CLI commands |
| **Command execution** | < 30ms each | Direct engine call (no subprocess) |
| **Memory overhead** | < 10MB | Per protocol render |

### Bottlenecks

1. **CLI command execution**: Network/disk I/O for object queries
2. **Markdown parsing**: Negligible (< 1ms for typical protocol)
3. **Result injection**: String manipulation (< 5ms)

### Optimization (Future)

- **Cache read-only commands**: Store results for 60 seconds
- **Parallel execution**: Run independent commands concurrently
- **Lazy rendering**: Only render sections agent navigates to

---

## 9. Implementation Status

**Status**: IMPLEMENTED - v1.0 complete, ready for open-source release

### Current Iteration (v1.0)

✅ **Completed**:
- Protocol specification and documentation (this document)
- Analysis of evolution from static to dynamic guides
- Design for protocol runtime resolution mechanism
- CLI command syntax standardization
- **Command renderer implementation** (`libs/environment/aware_environment/runtime/command_renderer.py`)
- **Protocol renderer implementation** (`libs/environment/aware_environment/protocol/renderer.py`)
- **Three-tier command grammar** (exec/required/suggested modes)
- **Intelligent selector/argument separation** based on function spec metadata
- **Command execution with logging** for visual flow validation
- **Unit tests** (25 tests for command_renderer)
- **Integration tests** (5 tests with lint-fixer samples)
- **Sample protocols** (`tests/samples/` with lint-fixer demonstration)

🎯 **Validated**:
- 30/30 tests passing (25 unit + 5 integration)
- Logging shows clear execution flow
- Real-world lint-fixer protocol demonstrates AI-guided code fixing
- Generic samples (not kernel-specific) ready for reuse

📋 **Planned (v1.1)**:
- Thread registry foundation
- Thread-Protocol linkage
- Protocol activation on thread join
- Agent protocol request API
- Kernel-specific protocols (agent-identity, task-adi)

### Future Iterations

**v2.0** (Variable Interpolation):
- `{{context.var}}` syntax for dynamic values
- Conditional blocks (`{% if %}`)
- Multi-command sequences with dependencies
- Result caching for read-only commands

**v3.0** (Thread Integration):
- Thread registry with protocol declarations
- Automatic protocol activation on thread join
- Protocol-guided agent onboarding flows
- Environment seed mechanism (boot thread creation)

---

## 10. Usage Examples

### For Agents

**Request a protocol**:
```python
# Agent requests bootstrap protocol
from aware_environment.renderer import render_protocol

protocol_text = render_protocol(slug="bootstrap")
# Returns rendered markdown with live command results
```

**Follow protocol guidance**:
1. Read protocol sections sequentially
2. Interpret injected command outputs
3. Make decisions based on live data
4. Execute protocol-suggested actions
5. Reference protocol in working memory

### For Environment Developers

**Create a new protocol**:

1. **Write template** in `environments/<env>/protocols/templates/`:
```markdown
# My Protocol

## Step 1: Discovery
```
object list --type <object>
```

Analyze results...
```

2. **Register protocol** in environment initialization:
```python
register_protocol(ProtocolSpec(
    slug="my-protocol",
    environment_slug="kernel",
    path="protocols/templates/my-protocol.md"
))
```

3. **Test rendering**:
```bash
aware-cli object call --type environment \
  --function render-protocol -- --slug my-protocol
```

### For CLI Users

**Render a protocol**:
```bash
# Render bootstrap protocol with live data
aware-cli object call --type environment \
  --function render-protocol -- --slug bootstrap --write protocol-output.md
```

**List available protocols**:
```bash
# Discover protocols in environment
aware-cli object list --type protocol
```

---

## 11. Integration with AWARE Architecture

### Constitution Alignment (Rule 00)

Protocols extend the **Thread/Object/Agent model**:

- **Threads** provide execution scope and advertise protocols
- **Objects** expose functions that protocols invoke
- **Agents** consume protocols for context resolution
- **Protocols** orchestrate the Object→Agent information flow

### ADI Workflow (Rule 02)

Protocol development follows Analysis-Design-Implementation:

1. **Analysis**: Capture protocol requirements and evolution reasoning
2. **Design**: Define protocol structure and command patterns
3. **Implementation**: Create template, register, test rendering

### Receipt Integration

Protocol rendering does NOT generate receipts (read-only operation). However:

- Commands executed BY protocols generate receipts normally
- Agents should reference protocol slug in working memory when following protocols
- Future: Protocol activation could generate `thread.protocol.activate` receipt

---

## 12. Testing Strategy

### Unit Tests

**File**: `libs/environment/tests/protocol/test_renderer.py`

```python
def test_parse_protocol_commands():
    """Extract CLI commands from protocol markdown."""
    markdown = """
    ## Step 1
    ```
    object list --type thread
    ```
    """
    commands = parse_protocol_commands(markdown)
    assert len(commands) == 1
    assert commands[0].command == "object list --type thread"

def test_execute_protocol_command():
    """Execute simple command and verify output."""
    result = execute_protocol_command("object list --type thread")
    assert result.success
    assert result.output  # Should contain JSON output

def test_render_protocol():
    """Full flow: template → rendered with results."""
    rendered = render_protocol("bootstrap")
    assert "Output:" in rendered
    assert "thread" in rendered.lower()
```

### Integration Tests

**File**: `libs/environment/tests/protocol/test_integration.py`

```python
def test_bootstrap_protocol_rendering():
    """Render bootstrap protocol with real CLI commands."""
    protocol_md = render_protocol("bootstrap", context={"process": "kernel"})

    # Verify structure preserved
    assert "# Bootstrap Protocol" in protocol_md
    assert "## Phase 1: Thread Discovery" in protocol_md

    # Verify commands executed
    assert "Output:" in protocol_md

    # Verify real data injected
    assert "thread" in protocol_md.lower()
    assert "id" in protocol_md
```

---

## 13. Migration Path

### For Existing Protocols

1. **Update syntax**: Remove `aware-cli` prefix from commands
2. **Remove `current/` directory**: Delete runtime snapshots
3. **Keep only templates**: Single source in `protocols/templates/`
4. **Test rendering**: Verify commands execute correctly

**Before**:
```markdown
Run this command:
```bash
aware-cli object list --type thread
```
```

**After**:
```markdown
Discover threads:
```
object list --type thread
```
```

### For New Protocols

1. Start with template in `protocols/templates/`
2. Use code blocks without language tags for CLI commands
3. Use exact CLI syntax (no `aware-cli` prefix)
4. Test with `render_protocol()` function
5. Register in environment

---

## 14. FAQ

### Q: Why not use subprocess to execute commands?
**A**: Direct CLI engine calls are faster, more secure (no shell injection), and provide better error handling. We control the execution environment completely.

### Q: Can protocols call external APIs?
**A**: Only through registered object functions. If an object exposes an API call, protocols can use it. This maintains security boundaries.

### Q: How do protocols handle errors?
**A**: Failed commands inject error output into the protocol. Agents see the error and can adapt. Future: Error recovery strategies in protocol templates.

### Q: Can one protocol call another?
**A**: Not in v1.0. Future: Protocol composition via `{% include protocol:slug %}` syntax.

### Q: How do variable interpolations work?
**A**: Not in v1.0. v2.0 will support `{{context.var}}` syntax for dynamic values passed during rendering.

---

This protocol framework enables AI agents to operate autonomously by providing them with live runtime context through executable guides. By combining procedural guidance with real-time state injection, protocols transform static documentation into dynamic AI-native context resolution systems.
