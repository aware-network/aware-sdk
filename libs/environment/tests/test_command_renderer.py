"""Tests for command execution and result injection in markdown rendering."""

from __future__ import annotations

import json
import pytest
from unittest.mock import Mock

from aware_environment.runtime.command_renderer import (
    CommandBlock,
    CommandResult,
    parse_command_blocks,
    parse_command_string,
    execute_command,
    inject_command_results,
    render_with_command_execution,
)
from aware_environment.runtime.executor import FunctionCallRequest, FunctionCallResult


# ---------------------------------------------------------------------------
# Phase 1: Parsing Tests
# ---------------------------------------------------------------------------


def test_parse_command_blocks_single_command():
    """Extract single command block from markdown."""
    markdown = """
# Example

Some text before.

```
object list --type thread
```

Some text after.
"""
    blocks = parse_command_blocks(markdown)

    assert len(blocks) == 1
    assert blocks[0].command == "object list --type thread"
    assert blocks[0].start_line == 5
    assert blocks[0].end_line == 7


def test_parse_command_blocks_multiple_commands():
    """Extract multiple command blocks."""
    markdown = """
## Step 1
```
object list --type thread
```

## Step 2
```
thread describe --id abc123
```
"""
    blocks = parse_command_blocks(markdown)

    assert len(blocks) == 2
    assert blocks[0].command == "object list --type thread"
    assert blocks[1].command == "thread describe --id abc123"


def test_parse_command_blocks_ignores_language_tagged():
    """Ignore code blocks with language tags."""
    markdown = """
Standard code:
```python
print("hello")
```

Command:
```
object list --type thread
```

More code:
```bash
echo "test"
```
"""
    blocks = parse_command_blocks(markdown)

    # Should only extract the command block (no language tag)
    assert len(blocks) == 1
    assert blocks[0].command == "object list --type thread"


def test_parse_command_blocks_empty_markdown():
    """Handle markdown with no command blocks."""
    markdown = """
# Just Text

No commands here.

```python
# This has a language tag
print("test")
```
"""
    blocks = parse_command_blocks(markdown)

    assert len(blocks) == 0


def test_parse_command_blocks_multiline_command():
    """Handle multiline commands."""
    markdown = """
```
object call --type task --id my-task
--function describe
```
"""
    blocks = parse_command_blocks(markdown)

    assert len(blocks) == 1
    assert "object call --type task --id my-task" in blocks[0].command
    assert "--function describe" in blocks[0].command


# ---------------------------------------------------------------------------
# Phase 2: Execution Tests
# ---------------------------------------------------------------------------


def test_parse_command_string_simple():
    """Parse simple command string."""
    obj_type, func_name, args = parse_command_string("object list --type thread")

    assert obj_type == "object"
    assert func_name == "list"
    assert args == {"type": "thread"}


def test_parse_command_string_multiple_args():
    """Parse command with multiple arguments."""
    obj_type, func_name, args = parse_command_string(
        "thread describe --id abc123 --format json"
    )

    assert obj_type == "thread"
    assert func_name == "describe"
    assert args == {"id": "abc123", "format": "json"}


def test_parse_command_string_boolean_flag():
    """Parse command with boolean flag."""
    obj_type, func_name, args = parse_command_string("object list --all")

    assert obj_type == "object"
    assert func_name == "list"
    assert args == {"all": True}


def test_parse_command_string_invalid_format():
    """Raise error on invalid command format."""
    with pytest.raises(ValueError, match="Invalid command format"):
        parse_command_string("object")  # Missing function name


def test_execute_command_success():
    """Execute command successfully through executor."""
    from aware_environment.object.spec import ObjectSpec, ObjectFunctionSpec

    # Mock executor with environment and specs
    mock_executor = Mock()

    # Mock object spec with list function (no selectors)
    mock_function_spec = ObjectFunctionSpec(
        name="list",
        metadata={"selectors": ()},  # Empty selectors for list operations
    )
    mock_object_spec = ObjectSpec(
        description="Test object",
        type="object",
        functions=[mock_function_spec],
    )

    # Mock environment
    mock_env = Mock()
    mock_env.objects.get.return_value = mock_object_spec
    mock_executor._environment = mock_env

    # Mock execution result
    mock_result = FunctionCallResult(
        payload={"id": "thread-001", "slug": "kernel/boot"},
        receipts=[],
        journal=[],
        rule_ids=(),
        selectors={},
    )
    mock_executor.execute.return_value = mock_result

    result = execute_command(mock_executor, "object list --type thread")

    assert result.success
    assert result.command == "object list --type thread"
    assert "thread-001" in result.output
    assert "kernel/boot" in result.output

    # Verify executor was called with correct request
    call_args = mock_executor.execute.call_args[0][0]
    assert isinstance(call_args, FunctionCallRequest)
    assert call_args.object_type == "object"
    assert call_args.function_name == "list"
    assert call_args.selectors == {}  # No selectors for list
    assert call_args.arguments == {"type": "thread"}  # Goes to arguments


def test_execute_command_error():
    """Handle command execution errors gracefully."""
    from aware_environment.object.spec import ObjectSpec, ObjectFunctionSpec

    mock_executor = Mock()

    # Mock for environment lookup failure
    mock_env = Mock()
    mock_env.objects.get.side_effect = ValueError("Unknown object type")
    mock_executor._environment = mock_env

    result = execute_command(mock_executor, "invalid command --foo bar")

    assert not result.success
    assert result.error is not None
    assert "Unknown object type" in result.error or "Invalid command format" in result.error


# ---------------------------------------------------------------------------
# Phase 3: Injection Tests
# ---------------------------------------------------------------------------


def test_inject_command_results_single():
    """Inject single command result."""
    markdown = """
# Test
```
object list --type thread
```
"""

    block = CommandBlock(start_line=2, end_line=4, command="object list --type thread")
    result = CommandResult(
        command="object list --type thread",
        output='[{"id": "thread-001"}]',
        success=True,
    )

    rendered = inject_command_results(markdown, [(block, result)])

    assert "object list --type thread" in rendered
    assert "Output:" in rendered
    assert '[{"id": "thread-001"}]' in rendered


def test_inject_command_results_error():
    """Inject error result."""
    markdown = """
```
invalid command
```
"""

    block = CommandBlock(start_line=1, end_line=3, command="invalid command")
    result = CommandResult(
        command="invalid command",
        output="",
        success=False,
        error="Unknown command",
    )

    rendered = inject_command_results(markdown, [(block, result)])

    assert "invalid command" in rendered
    assert "Error:" in rendered
    assert "Unknown command" in rendered


def test_inject_command_results_preserves_structure():
    """Preserve markdown structure around commands."""
    markdown = """
# Heading

Text before command.

```
object list --type thread
```

Text after command.

## Another Section
"""

    block = CommandBlock(start_line=5, end_line=7, command="object list --type thread")
    result = CommandResult(
        command="object list --type thread",
        output="[]",
        success=True,
    )

    rendered = inject_command_results(markdown, [(block, result)])

    assert "# Heading" in rendered
    assert "Text before command." in rendered
    assert "Text after command." in rendered
    assert "## Another Section" in rendered


# ---------------------------------------------------------------------------
# Full Pipeline Tests
# ---------------------------------------------------------------------------


def test_render_with_command_execution_full_pipeline():
    """Test full rendering pipeline."""
    from aware_environment.object.spec import ObjectSpec, ObjectFunctionSpec

    markdown = """
# Protocol Example

Discover threads:
```
object list --type thread
```

Done.
"""

    # Mock executor with environment
    mock_executor = Mock()

    # Mock object spec
    mock_function_spec = ObjectFunctionSpec(
        name="list",
        metadata={"selectors": ()},
    )
    mock_object_spec = ObjectSpec(
        description="Test object",
        type="object",
        functions=[mock_function_spec],
    )
    mock_env = Mock()
    mock_env.objects.get.return_value = mock_object_spec
    mock_executor._environment = mock_env

    # Mock execution result
    mock_result = FunctionCallResult(
        payload=[{"id": "thread-001", "slug": "kernel/boot"}],
        receipts=[],
        journal=[],
        rule_ids=(),
        selectors={},
    )
    mock_executor.execute.return_value = mock_result

    rendered = render_with_command_execution(markdown, mock_executor)

    # Should contain original command
    assert "object list --type thread" in rendered

    # Should contain output
    assert "Output:" in rendered
    assert "thread-001" in rendered
    assert "kernel/boot" in rendered

    # Should preserve structure
    assert "# Protocol Example" in rendered
    assert "Discover threads:" in rendered
    assert "Done." in rendered


def test_render_with_command_execution_no_commands():
    """Handle markdown without commands."""
    markdown = """
# Just Text

No commands here.
"""

    mock_executor = Mock()
    rendered = render_with_command_execution(markdown, mock_executor)

    # Should return unchanged
    assert rendered == markdown

    # Executor should not be called
    mock_executor.execute.assert_not_called()


def test_render_with_command_execution_multiple_commands():
    """Render markdown with multiple commands."""
    from aware_environment.object.spec import ObjectSpec, ObjectFunctionSpec

    markdown = """
## Step 1
```
object list --type thread
```

## Step 2
```
object list --type agent
```
"""

    # Mock executor with environment
    mock_executor = Mock()

    # Mock object spec
    mock_function_spec = ObjectFunctionSpec(
        name="list",
        metadata={"selectors": ()},
    )
    mock_object_spec = ObjectSpec(
        description="Test object",
        type="object",
        functions=[mock_function_spec],
    )
    mock_env = Mock()
    mock_env.objects.get.return_value = mock_object_spec
    mock_executor._environment = mock_env

    # First call returns threads, second returns agents
    mock_executor.execute.side_effect = [
        FunctionCallResult(
            payload=[{"id": "thread-001"}],
            receipts=[],
            journal=[],
            rule_ids=(),
            selectors={},
        ),
        FunctionCallResult(
            payload=[{"id": "agent-001"}],
            receipts=[],
            journal=[],
            rule_ids=(),
            selectors={},
        ),
    ]

    rendered = render_with_command_execution(markdown, mock_executor)

    # Both outputs should be present
    assert "thread-001" in rendered
    assert "agent-001" in rendered

    # Structure preserved
    assert "## Step 1" in rendered
    assert "## Step 2" in rendered

    # Executor called twice
    assert mock_executor.execute.call_count == 2


# ---------------------------------------------------------------------------
# Command Grammar Tests
# ---------------------------------------------------------------------------


def test_parse_command_mode_exec():
    """Parse command with exec mode marker."""
    markdown = """
<!-- command:exec -->
```
object list --type thread
```
"""
    blocks = parse_command_blocks(markdown)
    assert len(blocks) == 1
    assert blocks[0].mode == "exec"


def test_parse_command_mode_required():
    """Parse command with required mode marker."""
    markdown = """
<!-- command:required -->
```
code write --path file.py
```
"""
    blocks = parse_command_blocks(markdown)
    assert len(blocks) == 1
    assert blocks[0].mode == "required"


def test_parse_command_mode_suggested():
    """Parse command with suggested mode marker."""
    markdown = """
<!-- command:suggested -->
```
code lint --path file.py
```
"""
    blocks = parse_command_blocks(markdown)
    assert len(blocks) == 1
    assert blocks[0].mode == "suggested"


def test_parse_command_mode_default():
    """Default to exec when no marker specified."""
    markdown = """
```
object list --type thread
```
"""
    blocks = parse_command_blocks(markdown)
    assert len(blocks) == 1
    assert blocks[0].mode == "exec"


def test_render_exec_mode_executes():
    """Exec mode commands are executed."""
    from aware_environment.object.spec import ObjectSpec, ObjectFunctionSpec

    markdown = """
<!-- command:exec -->
```
object list --type thread
```
"""
    mock_executor = Mock()
    mock_function_spec = ObjectFunctionSpec(name="list", metadata={"selectors": ()})
    mock_object_spec = ObjectSpec(description="Test", type="object", functions=[mock_function_spec])
    mock_env = Mock()
    mock_env.objects.get.return_value = mock_object_spec
    mock_executor._environment = mock_env
    mock_executor.execute.return_value = FunctionCallResult(
        payload=[{"id": "thread-001"}], receipts=[], journal=[], rule_ids=(), selectors={}
    )

    rendered = render_with_command_execution(markdown, mock_executor)

    assert "Output:" in rendered
    assert "thread-001" in rendered
    mock_executor.execute.assert_called_once()


def test_render_required_mode_skips():
    """Required mode commands are not executed."""
    markdown = """
<!-- command:required -->
```
code write --path file.py
```
"""
    mock_executor = Mock()
    rendered = render_with_command_execution(markdown, mock_executor)

    # Should not execute command
    mock_executor.execute.assert_not_called()
    # Should preserve command block
    assert "code write --path file.py" in rendered
    # Should not have output
    assert "Output:" not in rendered


def test_render_suggested_mode_skips():
    """Suggested mode commands are not executed."""
    markdown = """
<!-- command:suggested -->
```
code lint --path file.py
```
"""
    mock_executor = Mock()
    rendered = render_with_command_execution(markdown, mock_executor)

    # Should not execute command
    mock_executor.execute.assert_not_called()
    # Should preserve command block
    assert "code lint --path file.py" in rendered
    # Should not have output
    assert "Output:" not in rendered


def test_render_mixed_modes():
    """Mix of exec/required/suggested modes."""
    from aware_environment.object.spec import ObjectSpec, ObjectFunctionSpec

    markdown = """
<!-- command:exec -->
```
object list --type thread
```

<!-- command:required -->
```
code write --path file.py
```

<!-- command:suggested -->
```
code lint --path file.py
```
"""
    mock_executor = Mock()
    mock_function_spec = ObjectFunctionSpec(name="list", metadata={"selectors": ()})
    mock_object_spec = ObjectSpec(description="Test", type="object", functions=[mock_function_spec])
    mock_env = Mock()
    mock_env.objects.get.return_value = mock_object_spec
    mock_executor._environment = mock_env
    mock_executor.execute.return_value = FunctionCallResult(
        payload=[{"id": "thread-001"}], receipts=[], journal=[], rule_ids=(), selectors={}
    )

    rendered = render_with_command_execution(markdown, mock_executor)

    # Exec should have output
    assert "thread-001" in rendered
    # Required should be preserved
    assert "code write --path file.py" in rendered
    # Suggested should be preserved
    assert "code lint --path file.py" in rendered
    # Only one execution (exec mode)
    mock_executor.execute.assert_called_once()
