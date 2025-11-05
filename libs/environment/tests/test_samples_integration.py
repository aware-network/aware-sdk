"""Integration tests with sample protocol, object, and workspace."""

from pathlib import Path

import pytest

from aware_environment import Environment
from aware_environment.runtime.command_renderer import render_with_command_execution
from aware_environment.runtime.executor import ObjectExecutor


@pytest.fixture
def code_environment():
    """Environment with code object registered."""
    # Import code object spec
    import sys
    samples_dir = Path(__file__).parent / "samples"
    sys.path.insert(0, str(samples_dir / "objects"))

    from code_object import CODE_OBJECT_SPEC

    env = Environment.empty()
    env.bind_objects([CODE_OBJECT_SPEC])
    return env


def test_lint_fixer_protocol_integration(code_environment):
    """Test full lint-fixer protocol with real code object."""
    print("\n" + "=" * 80)
    print("LINT-FIXER PROTOCOL: AI-Guided Code Quality Improvement")
    print("=" * 80)

    # Load protocol
    protocol_path = Path(__file__).parent / "samples" / "protocols" / "lint-fixer.md"
    protocol_md = protocol_path.read_text()
    print("\n📄 Loaded protocol: lint-fixer.md")
    print("   - Step 1-2: EXEC mode (auto-execute, inject live state)")
    print("   - Step 3: REQUIRED mode (AI must fix)")
    print("   - Step 4-5: SUGGESTED mode (AI can verify/format)")

    # Render with command execution
    print("\n⚙️  Rendering protocol with command execution...")
    executor = ObjectExecutor(code_environment)
    rendered = render_with_command_execution(protocol_md, executor)

    print("\n✅ Step 1 (EXEC): Read code → Live content injected")
    print("   Found: 'import os', 'def greet( name )'")

    print("\n✅ Step 2 (EXEC): Run linter → Live errors injected")
    if "unused import" in rendered:
        print("   Error 1: unused import 'os'")
    if "unexpected whitespace" in rendered or "line" in rendered:
        print("   Error 2: spacing issue in function signature")

    print("\n⏭️  Step 3 (REQUIRED): AI must fix code (not executed)")
    print("   Command preserved for AI: code write --path sample.py")

    print("\n⏭️  Step 4-5 (SUGGESTED): AI can verify/format (not executed)")
    print("   Commands preserved for AI consideration")

    print("\n" + "=" * 80)
    print("RESULT: AI sees live lint errors → knows exactly what to fix")
    print("=" * 80 + "\n")

    # Verify exec commands executed
    assert "Output:" in rendered  # At least one exec command ran

    # Verify code content injected
    assert "import os" in rendered  # From Step 1: read
    assert "def greet" in rendered

    # Verify lint errors injected
    assert "unused import" in rendered or "line" in rendered  # From Step 2: lint

    # Verify required/suggested blocks preserved (not executed)
    assert "code write --path sample.py" in rendered  # Step 3: required
    assert "code lint --path sample.py" in rendered  # Step 4: suggested
    assert "code format --path sample.py" in rendered  # Step 5: suggested

    # Count Output sections (should be 2: read + lint)
    output_count = rendered.count("Output:")
    assert output_count == 2  # Only exec commands have output


def test_exec_mode_injects_results(code_environment):
    """Exec mode commands inject live results."""
    print("\n🔄 EXEC MODE: Auto-execute and inject results")
    protocol = """
<!-- command:exec -->
```
code read --path sample.py
```
"""
    executor = ObjectExecutor(code_environment)
    rendered = render_with_command_execution(protocol, executor)
    print("   ✅ Command executed, live results injected\n")

    assert "Output:" in rendered
    assert "import os" in rendered  # Actual file content


def test_required_mode_skips_execution(code_environment):
    """Required mode commands are not executed."""
    print("\n❗ REQUIRED MODE: AI must execute (not auto-run)")
    protocol = """
<!-- command:required -->
```
code write --path sample.py --content test
```
"""
    executor = ObjectExecutor(code_environment)
    rendered = render_with_command_execution(protocol, executor)
    print("   ⏭️  Skipped execution, command preserved for AI\n")

    # Should NOT have output
    assert "Output:" not in rendered
    # Should preserve command
    assert "code write --path sample.py" in rendered


def test_suggested_mode_skips_execution(code_environment):
    """Suggested mode commands are not executed."""
    print("\n💡 SUGGESTED MODE: AI can execute (optional)")
    protocol = """
<!-- command:suggested -->
```
code lint --path sample.py
```
"""
    executor = ObjectExecutor(code_environment)
    rendered = render_with_command_execution(protocol, executor)
    print("   ⏭️  Skipped execution, command suggested to AI\n")

    # Should NOT have output
    assert "Output:" not in rendered
    # Should preserve command
    assert "code lint --path sample.py" in rendered


def test_mixed_modes_in_protocol(code_environment):
    """Protocol with mixed exec/required/suggested modes."""
    print("\n🎯 MIXED MODES: All three command types in one protocol")
    protocol = """
<!-- command:exec -->
```
code read --path sample.py
```

<!-- command:required -->
```
code write --path sample.py --content fixed
```

<!-- command:suggested -->
```
code format --path sample.py
```
"""
    executor = ObjectExecutor(code_environment)
    rendered = render_with_command_execution(protocol, executor)

    print("   ✅ EXEC: Executed and injected")
    print("   ❗ REQUIRED: Preserved for AI")
    print("   💡 SUGGESTED: Preserved for AI\n")

    # Exec should have output
    output_count = rendered.count("Output:")
    assert output_count == 1

    # Required and suggested should be preserved
    assert "code write --path sample.py" in rendered
    assert "code format --path sample.py" in rendered
