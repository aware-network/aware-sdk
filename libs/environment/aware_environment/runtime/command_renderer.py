"""Command execution and result injection for markdown rendering.

This module provides reusable utilities for executing embedded commands in markdown
and injecting their results. Commands can be any environment function call - not limited
to CLI operations.

Future extensions may include:
- Network operations via function calls
- Graph queries
- Cross-environment function invocation
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

if TYPE_CHECKING:
    from .executor import ObjectExecutor

logger = logging.getLogger(__name__)


@dataclass
class CommandBlock:
    """A command block extracted from markdown."""

    start_line: int
    end_line: int
    command: str
    mode: str = "exec"
    indent: str = ""


@dataclass
class CommandResult:
    """Result of command execution."""

    command: str
    output: str
    success: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 1: Parsing
# ---------------------------------------------------------------------------


def parse_command_blocks(markdown: str) -> List[CommandBlock]:
    """Extract command blocks from markdown.

    Command blocks are code blocks without language tags:

    ```
    object list --type thread
    ```

    Standard code blocks with language tags are ignored:

    ```python
    print("hello")
    ```

    Parameters
    ----------
    markdown:
        Markdown content to parse

    Returns
    -------
    List of CommandBlock objects with line positions and command text
    """
    blocks: List[CommandBlock] = []
    lines = markdown.splitlines()
    in_command_block = False
    in_other_block = False
    current_block: List[str] = []
    start_line: Optional[int] = None
    command_mode = "exec"  # Default mode

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect command mode marker: <!-- command:MODE -->
        if stripped.startswith("<!-- command:") and stripped.endswith("-->"):
            mode_text = stripped[13:-3].strip()
            if mode_text in ("exec", "required", "suggested"):
                command_mode = mode_text
            continue

        # Start of code block
        if stripped.startswith("```") and not in_command_block and not in_other_block:
            # If line is exactly "```" with no language, it's a command block
            if stripped == "```":
                in_command_block = True
                start_line = i
                current_block = []
            else:
                # Has language tag - skip this entire block
                in_other_block = True
                command_mode = "exec"  # Reset mode
            continue

        # End of command block
        elif stripped == "```" and in_command_block:
            if start_line is not None:
                command_text = "\n".join(current_block)
                blocks.append(
                    CommandBlock(
                        start_line=start_line,
                        end_line=i,
                        command=command_text.strip(),
                        mode=command_mode,
                        indent="",
                    )
                )
            in_command_block = False
            start_line = None
            current_block = []
            command_mode = "exec"  # Reset to default

        # End of other (language-tagged) block
        elif stripped.startswith("```") and in_other_block:
            in_other_block = False

        # Collect command content
        elif in_command_block:
            current_block.append(line)

    logger.info(f"Parsed {len(blocks)} command blocks from markdown")
    for block in blocks:
        logger.info(f"  Block [{block.start_line}:{block.end_line}] mode={block.mode}: {block.command[:50]}...")

    return blocks


# ---------------------------------------------------------------------------
# Phase 2: Execution
# ---------------------------------------------------------------------------


def parse_command_string(command: str) -> Tuple[str, str, dict[str, Any]]:
    """Parse command string into object type, function name, and arguments.

    Examples:
        "object list --type thread" → ("object", "list", {"type": "thread"})
        "thread describe --id abc123" → ("thread", "describe", {"id": "abc123"})

    Parameters
    ----------
    command:
        Command string to parse

    Returns
    -------
    Tuple of (object_type, function_name, arguments_dict)

    Raises
    ------
    ValueError:
        If command format is invalid
    """
    parts = command.split()
    if len(parts) < 2:
        raise ValueError(f"Invalid command format: {command}")

    object_type = parts[0]
    function_name = parts[1]

    # Parse flags (--key value patterns)
    args: dict[str, Any] = {}
    i = 2
    while i < len(parts):
        if parts[i].startswith("--"):
            key = parts[i][2:]  # Remove "--"
            if i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                args[key] = parts[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            i += 1

    return object_type, function_name, args


def execute_command(executor: ObjectExecutor, command: str) -> CommandResult:
    """Execute command through ObjectExecutor.

    Intelligently separates selectors from arguments based on function spec metadata.

    Parameters
    ----------
    executor:
        Environment object executor
    command:
        Command string to execute

    Returns
    -------
    CommandResult with output or error message
    """
    logger.info(f"Executing command: {command}")
    try:
        from .executor import FunctionCallRequest

        object_type, function_name, parsed_args = parse_command_string(command)

        # Get specs from environment to determine selectors
        env = executor._environment
        object_spec = env.objects.get(object_type)
        function_spec = next(
            (f for f in object_spec.functions if f.name == function_name),
            None,
        )

        if not function_spec:
            raise ValueError(f"Unknown function: {object_type}.{function_name}")

        # Get selector names from function metadata
        metadata = function_spec.metadata or {}
        selector_names = set(metadata.get("selectors") or ())

        # Separate selectors from arguments based on function spec
        selectors: dict[str, Any] = {}
        arguments: dict[str, Any] = {}

        for key, value in parsed_args.items():
            # Normalize key (--foo-bar → foo_bar) for matching
            normalized_key = key.replace("-", "_")

            # Check if this parameter is a selector
            if normalized_key in selector_names:
                selectors[normalized_key] = value
            else:
                arguments[key] = value

        logger.info(f"  {object_type}.{function_name} selectors={selectors} arguments={arguments}")

        # Build and execute request
        request = FunctionCallRequest(
            object_type=object_type,
            function_name=function_name,
            selectors=selectors,
            arguments=arguments,
        )

        result = executor.execute(request)

        # Format output
        if result.payload:
            output = json.dumps(result.payload, indent=2)
        else:
            output = ""

        logger.info(f"  ✓ Command succeeded (output: {len(output)} chars)")

        return CommandResult(
            command=command,
            output=output,
            success=True,
            error=None,
        )

    except Exception as e:
        logger.warning(f"  ✗ Command failed: {e}")
        return CommandResult(
            command=command,
            output="",
            success=False,
            error=str(e),
        )


# ---------------------------------------------------------------------------
# Phase 3: Injection
# ---------------------------------------------------------------------------


def inject_command_results(
    markdown: str,
    results: List[Tuple[CommandBlock, Optional[CommandResult]]],
) -> str:
    """Replace command blocks with command + output.

    Parameters
    ----------
    markdown:
        Original markdown content
    results:
        List of (CommandBlock, Optional[CommandResult]) tuples

    Returns
    -------
    Rendered markdown with command results injected
    """
    lines = markdown.splitlines()

    # Process in reverse order to preserve line numbers
    for block, result in reversed(results):
        if result is None:
            # Skip injection for required/suggested modes (leave as-is)
            continue

        if result.success:
            replacement = [
                "```",
                block.command,
                "```",
                "",
                "Output:",
                "```",
                result.output.strip(),
                "```",
            ]
        else:
            replacement = [
                "```",
                block.command,
                "```",
                "",
                "Error:",
                "```",
                result.error or "Unknown error",
                "```",
            ]

        # Replace block lines
        lines[block.start_line : block.end_line + 1] = replacement

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_with_command_execution(
    markdown: str,
    executor: ObjectExecutor,
) -> str:
    """Render markdown with command execution and result injection.

    This is the main public API for command rendering. It:
    1. Parses command blocks from markdown (code blocks without language tags)
    2. Executes each command through the environment executor
    3. Injects results back into markdown
    4. Returns rendered markdown

    Command blocks are identified by code blocks without language tags:

    ```
    object list --type thread
    ```

    After rendering, they become:

    ```
    object list --type thread
    ```

    Output:
    ```
    [{"id": "...", "slug": "kernel/boot"}]
    ```

    Parameters
    ----------
    markdown:
        Markdown content with embedded command blocks
    executor:
        Environment object executor for command execution

    Returns
    -------
    Rendered markdown with command results injected

    Examples
    --------
    >>> from aware_environment.runtime.executor import ObjectExecutor
    >>> executor = ObjectExecutor(environment)
    >>> rendered = render_with_command_execution(markdown, executor)
    """
    logger.info("=" * 80)
    logger.info("RENDER WITH COMMAND EXECUTION")
    logger.info("=" * 80)

    # Parse command blocks
    command_blocks = parse_command_blocks(markdown)

    if not command_blocks:
        logger.info("No command blocks found, returning markdown as-is")
        return markdown  # No commands, return as-is

    # Execute commands (only exec mode)
    logger.info(f"\nProcessing {len(command_blocks)} command blocks:")
    results: List[Tuple[CommandBlock, Optional[CommandResult]]] = []
    for block in command_blocks:
        if block.mode == "exec":
            logger.info(f"\n[EXEC] Executing block at lines {block.start_line}-{block.end_line}")
            result = execute_command(executor, block.command)
            results.append((block, result))
        else:
            # Skip execution for required/suggested modes
            logger.info(f"\n[{block.mode.upper()}] Skipping execution at lines {block.start_line}-{block.end_line}")
            logger.info(f"  Command: {block.command[:50]}...")
            results.append((block, None))

    # Inject results
    logger.info("\nInjecting results into markdown...")
    rendered = inject_command_results(markdown, results)
    logger.info(f"✓ Rendering complete\n")

    return rendered
