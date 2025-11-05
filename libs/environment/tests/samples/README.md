# Environment Test Samples

Generic samples for validating command_renderer capabilities.

## Structure

```
samples/
├── protocols/
│   └── lint-fixer.md       # Protocol demonstrating exec/required/suggested modes
├── objects/
│   └── code.py             # Code object with read/lint/write/format functions
└── workspace/
    └── sample.py           # Python file with intentional lint errors
```

## Purpose

Validate command_renderer **mechanism** works:
- Parse command blocks with mode markers
- Execute `exec` mode commands
- Skip `required` and `suggested` modes
- Inject live results into protocols

## Lint-Fixer Protocol

Demonstrates real-world AI workflow:

1. **Step 1-2** (`exec`): Auto-read code, run linter, inject live errors
2. **Step 3** (`required`): AI must fix code based on actual errors
3. **Step 4-5** (`suggested`): AI can verify/format if appropriate

## Sample Code Errors

`workspace/sample.py` contains:
- Unused import (`import os`)
- Spacing issues (`def greet( name )` should be `def greet(name)`)

## Usage

```python
from aware_environment import Environment
from aware_environment.runtime.command_renderer import render_with_command_execution
from aware_environment.runtime.executor import ObjectExecutor
from tests.samples.objects.code import CODE_OBJECT_SPEC

# Setup environment
env = Environment()
env.bind_objects([CODE_OBJECT_SPEC])

# Render protocol with live lint errors
protocol_path = "tests/samples/protocols/lint-fixer.md"
protocol_md = Path(protocol_path).read_text()

executor = ObjectExecutor(env)
rendered = render_with_command_execution(protocol_md, executor)

# AI sees live lint errors, knows exactly what to fix
print(rendered)
```

## Value Proposition

**Without command_renderer**: AI must manually read file, run linter, parse errors
**With command_renderer**: AI sees pre-executed context, focuses on fixing

Clear ROI: Live state injection → Autonomous code fixing
