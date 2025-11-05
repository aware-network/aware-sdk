"""Protocol rendering with command execution.

Protocols are executable guides that combine procedural guidance with live runtime
state. This module renders protocol templates by executing embedded commands and
injecting their results.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..environment import Environment


def render_protocol(
    environment: Environment,
    slug: str,
    context: Optional[dict] = None,
) -> str:
    """Render protocol with live command execution.

    Loads a protocol template and renders it with embedded command execution.
    Commands in the template (code blocks without language tags) are executed
    through the environment's object executor and their results are injected
    into the rendered output.

    Parameters
    ----------
    environment:
        Environment containing protocol registry and object executor
    slug:
        Protocol slug to render
    context:
        Optional context for future variable interpolation (not yet implemented)

    Returns
    -------
    Rendered protocol markdown with command results injected

    Raises
    ------
    ValueError:
        If protocol with given slug is not found

    Examples
    --------
    >>> from aware_environment import Environment
    >>> env = Environment.load()
    >>> protocol_md = render_protocol(env, "bootstrap")
    """
    from ..runtime.command_renderer import render_with_command_execution
    from ..runtime.executor import ObjectExecutor

    # 1. Load protocol template
    protocol_spec = environment.protocols.get(slug)
    if protocol_spec is None:
        raise ValueError(f"Protocol '{slug}' not found in environment")

    template_path = Path(protocol_spec.path)
    if not template_path.exists():
        raise ValueError(f"Protocol template not found: {template_path}")

    markdown = template_path.read_text()

    # 2. Apply context interpolation (future: {{var}} replacement)
    if context:
        # Future: Replace {{context.process}} etc
        pass

    # 3. Render with command execution (delegates to common tooling)
    executor = ObjectExecutor(environment)
    rendered = render_with_command_execution(markdown, executor)

    return rendered
