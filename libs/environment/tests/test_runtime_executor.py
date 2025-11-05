from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from aware_environment.environment import Environment
from aware_environment.fs import (
    EnsureInstruction,
    OperationContext,
    OperationPlan,
    OperationWritePolicy,
    WriteInstruction,
)
from aware_environment.object.spec import ObjectFunctionSpec, ObjectSpec
from aware_environment.runtime.executor import FunctionCallRequest, ObjectExecutor


def _plan_handler(path: str, *, object_type: str = "demo-object") -> OperationPlan:
    target = Path(path)
    return OperationPlan(
        context=OperationContext(
            object_type=object_type,
            function="write",
            selectors={"path": str(target.name)},
        ),
        ensure_dirs=(EnsureInstruction(path=target.parent),),
        writes=(
            WriteInstruction(
                path=target,
                content="hello world\n",
                policy=OperationWritePolicy.MODIFIABLE,
                event="created",
                doc_type="test-doc",
                timestamp=datetime.now(timezone.utc),
                metadata={"path": str(target)},
            ),
        ),
    )


def test_executor_applies_operation_plan(tmp_path):
    env = Environment.empty()
    spec = ObjectSpec(
        type="demo-object",
        description="Demo object for executor tests",
        functions=(
            ObjectFunctionSpec(
                name="write",
                handler_factory=lambda: lambda path: _plan_handler(path, object_type="demo-object"),
                metadata={"rule_ids": ("demo-rule",)},
            ),
        ),
    )
    env.bind_objects([spec])

    executor = ObjectExecutor(env)
    target_path = tmp_path / "data" / "sample.txt"
    request = FunctionCallRequest(
        object_type="demo-object",
        function_name="write",
        selectors={"path": target_path.name},
        arguments={"path": str(target_path)},
    )

    result = executor.execute(request)

    assert target_path.exists()
    assert result.payload is None
    assert result.rule_ids == ("demo-rule",)
    assert result.receipts and result.receipts[0]["context"]["object_type"] == "demo-object"
    assert result.journal and result.journal[0]["action"] == "apply-plan"


def test_executor_handles_mapping_payload():
    env = Environment.empty()

    def handler(name: str) -> dict[str, str]:
        return {"greeting": f"hello {name}"}

    spec = ObjectSpec(
        type="simple-object",
        description="Simple object",
        functions=(
            ObjectFunctionSpec(
                name="greet",
                handler_factory=lambda: handler,
                metadata={},
            ),
        ),
    )
    env.bind_objects([spec])

    executor = ObjectExecutor(env)
    request = FunctionCallRequest(
        object_type="simple-object",
        function_name="greet",
        selectors={"name": "world"},
        arguments={"name": "world"},
    )

    result = executor.execute(request)

    assert result.payload == {"greeting": "hello world"}
    assert result.receipts == []
    assert result.journal == []
