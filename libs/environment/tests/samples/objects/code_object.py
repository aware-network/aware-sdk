"""Code object specification for sample tests."""

from pathlib import Path
from typing import Any, Dict, List

from aware_environment import ObjectSpec, ObjectFunctionSpec


def read_handler(path: str) -> Dict[str, Any]:
    """Read code file."""
    file_path = Path(__file__).parent.parent / "workspace" / path
    content = file_path.read_text()
    return {"path": path, "content": content}


def lint_handler(path: str) -> List[Dict[str, Any]]:
    """Lint code file (simple checks)."""
    file_path = Path(__file__).parent.parent / "workspace" / path
    content = file_path.read_text()

    errors = []
    for i, line in enumerate(content.splitlines(), 1):
        # Check for unused imports
        if "import os" in line and "os." not in content:
            errors.append({"line": i, "column": 1, "message": "unused import 'os'"})
        # Check for spacing issues
        if "def " in line and "( " in line:
            errors.append({"line": i, "column": line.index("("), "message": "unexpected whitespace after '('"})

    return errors


def write_handler(path: str, content: str) -> Dict[str, Any]:
    """Write code file."""
    file_path = Path(__file__).parent.parent / "workspace" / path
    file_path.write_text(content)
    return {"path": path, "bytes_written": len(content)}


def format_handler(path: str) -> Dict[str, Any]:
    """Format code file (mock)."""
    return {"path": path, "formatted": True}


CODE_OBJECT_SPEC = ObjectSpec(
    type="code",
    description="Code file operations for testing",
    functions=[
        ObjectFunctionSpec(
            name="read",
            handler_factory=lambda: read_handler,
            metadata={"selectors": (), "arguments": [{"name": "path"}]},
        ),
        ObjectFunctionSpec(
            name="lint",
            handler_factory=lambda: lint_handler,
            metadata={"selectors": (), "arguments": [{"name": "path"}]},
        ),
        ObjectFunctionSpec(
            name="write",
            handler_factory=lambda: write_handler,
            metadata={"selectors": (), "arguments": [{"name": "path"}, {"name": "content"}]},
        ),
        ObjectFunctionSpec(
            name="format",
            handler_factory=lambda: format_handler,
            metadata={"selectors": (), "arguments": [{"name": "path"}]},
        ),
    ],
)
