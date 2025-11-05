"""Typed executor for environment object functions."""

from __future__ import annotations

import dataclasses
import inspect
import importlib
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, ContextManager, Mapping, MutableMapping, Optional, Protocol

from ..environment import Environment
from ..exceptions import UnknownSpecError
from ..fs import OperationPlan, Receipt, apply_plan
from ..fs.receipt import EnsureOp, MoveOp, WriteOp
from ..object.spec import ObjectFunctionSpec, ObjectSpec


class SessionHandle(Protocol):
    """Protocol for filesystem session handles used by the executor."""

    def dump(self) -> Mapping[str, Any]: ...


SessionFactory = Callable[[Any], ContextManager[SessionHandle]]
PlanApplier = Callable[[OperationPlan], Receipt]


@dataclass(frozen=True)
class FunctionCallRequest:
    """Parameters describing an object function invocation."""

    object_type: str
    function_name: str
    selectors: Mapping[str, str]
    arguments: Mapping[str, Any] = field(default_factory=dict)
    session_config: Any | None = None
    context: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class FunctionCallResult:
    """Structured response produced by the executor."""

    payload: Any
    receipts: list[dict[str, Any]]
    journal: list[dict[str, Any]]
    rule_ids: tuple[str, ...]
    selectors: Mapping[str, str]
    warnings: tuple[str, ...] = ()


class HandlerResolutionError(RuntimeError):
    """Raised when a handler factory cannot be resolved."""


class ObjectExecutor:
    """Executes environment object functions with plan application and receipt synthesis."""

    def __init__(
        self,
        environment: Environment,
        *,
        session_factory: SessionFactory | None = None,
        plan_applier: PlanApplier = apply_plan,
    ) -> None:
        self._environment = environment
        self._session_factory = session_factory
        self._plan_applier = plan_applier

    def execute(self, request: FunctionCallRequest) -> FunctionCallResult:
        spec = self._resolve_object_spec(request.object_type)
        function_spec = self._resolve_function_spec(spec, request.function_name)
        handler = self._resolve_handler(function_spec)

        rule_ids = self._extract_rule_ids(function_spec)
        receipts: list[dict[str, Any]] = []
        journal: list[dict[str, Any]] = []

        session_cm: ContextManager[SessionHandle]
        if self._session_factory and request.session_config is not None:
            session_cm = self._session_factory(request.session_config)
        else:
            session_cm = nullcontext()  # type: ignore[arg-type]

        with session_cm as session_handle:  # type: ignore[assignment]
            payload, handler_receipts, handler_journal = self._invoke_handler(
                handler,
                spec,
                function_spec,
                request.arguments,
                request.selectors,
            )
            receipts.extend(handler_receipts)
            journal.extend(handler_journal)

            if session_handle is not None:
                session_dump = session_handle.dump()
                self._merge_session_records(receipts, journal, session_dump)

        return FunctionCallResult(
            payload=payload,
            receipts=receipts,
            journal=journal,
            rule_ids=rule_ids,
            selectors=dict(request.selectors),
        )

    def _resolve_object_spec(self, object_type: str) -> ObjectSpec:
        try:
            return self._environment.objects.get(object_type)
        except UnknownSpecError as exc:  # pragma: no cover - defensive
            raise exc

    def _resolve_function_spec(self, spec: ObjectSpec, function_name: str) -> ObjectFunctionSpec:
        for func in spec.functions:
            if func.name == function_name:
                return func
        raise UnknownSpecError(f"Function '{function_name}' not registered for object '{spec.type}'.")

    def _resolve_handler(self, function_spec: ObjectFunctionSpec) -> Callable[..., Any]:
        factory = function_spec.handler_factory
        if factory is None:
            raise HandlerResolutionError(f"No handler factory defined for function '{function_spec.name}'.")
        if callable(factory):
            try:
                handler_candidate = factory()
            except TypeError:
                return factory  # type: ignore[return-value]
            if callable(handler_candidate):
                return handler_candidate
            raise HandlerResolutionError(
                f"Handler factory for '{function_spec.name}' did not return a callable."
            )
        if isinstance(factory, str):
            if ":" not in factory:
                raise HandlerResolutionError(
                    f"Handler factory '{factory}' is not a callable and is missing the 'module:callable' format."
                )
            module_name, attr = factory.split(":", 1)
            module = importlib.import_module(module_name)
            handler = getattr(module, attr, None)
            if handler is None or not callable(handler):
                raise HandlerResolutionError(f"Callable '{factory}' could not be resolved.")
            return handler
        raise HandlerResolutionError(f"Unsupported handler factory type '{type(factory)}'.")

    def _invoke_handler(
        self,
        handler: Callable[..., Any],
        object_spec: ObjectSpec,
        function_spec: ObjectFunctionSpec,
        arguments: Mapping[str, Any],
        selectors: Mapping[str, str],
    ) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]]:
        call_args = dict(arguments)
        try:
            signature = inspect.signature(handler)
        except (TypeError, ValueError):
            signature = None

        if signature is not None:
            parameters = list(signature.parameters.values())
            needs_environment = (
                parameters
                and parameters[0].name == "environment"
                and parameters[0].kind
                in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            )
        else:
            needs_environment = False

        if needs_environment:
            result = handler(self._environment, **call_args)
        else:
            result = handler(**call_args)
        receipts: list[dict[str, Any]] = []
        journal: list[dict[str, Any]] = []

        def _apply_plan_and_capture(plan: OperationPlan) -> None:
            receipt = self._plan_applier(plan)
            receipt_dict = self._operation_receipt_to_dict(receipt)
            receipts.append(receipt_dict)
            journal.append(self._receipt_to_journal(receipt_dict))

        if isinstance(result, OperationPlan):
            _apply_plan_and_capture(result)
            payload: Any = None
        elif dataclasses.is_dataclass(result):
            plan_candidate = getattr(result, "plan", None)
            if isinstance(plan_candidate, OperationPlan):
                _apply_plan_and_capture(plan_candidate)
            plans_candidate = getattr(result, "plans", None)
            if plans_candidate is not None:
                for candidate_plan in plans_candidate if isinstance(plans_candidate, (list, tuple)) else [plans_candidate]:
                    if isinstance(candidate_plan, OperationPlan):
                        _apply_plan_and_capture(candidate_plan)
            if hasattr(result, "payload"):
                payload_attr = getattr(result, "payload")
                payload_value = payload_attr() if callable(payload_attr) else payload_attr
                payload = self._serialise(payload_value)
            else:
                payload = self._serialise(asdict(result))
        elif hasattr(result, "plan"):
            plan_candidate = getattr(result, "plan")
            if isinstance(plan_candidate, OperationPlan):
                _apply_plan_and_capture(plan_candidate)
            if hasattr(result, "result"):
                result_attr = getattr(result, "result")
                payload = self._serialise(result_attr() if callable(result_attr) else result_attr)
            else:
                payload = None
        else:
            payload = self._serialise(result)

        return payload, receipts, journal

    def _extract_rule_ids(self, function_spec: ObjectFunctionSpec) -> tuple[str, ...]:
        metadata = function_spec.metadata or {}
        rule_ids = metadata.get("rule_ids")
        if isinstance(rule_ids, (list, tuple)):
            return tuple(str(rule_id) for rule_id in rule_ids)
        if isinstance(rule_ids, str):
            return (rule_ids,)
        return tuple()

    def _serialise(self, value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")  # PyDantic models
        if dataclasses.is_dataclass(value):
            return asdict(value)
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if isinstance(value, Mapping):
            return {str(key): self._serialise(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._serialise(item) for item in value]
        if isinstance(value, tuple):
            return [self._serialise(item) for item in value]
        return value

    def _operation_receipt_to_dict(self, receipt: Receipt) -> dict[str, Any]:
        return {
            "schema": receipt.schema,
            "receipt_id": receipt.receipt_id,
            "timestamp": self._isoformat(receipt.timestamp),
            "context": {
                "object_type": receipt.context.object_type,
                "function": receipt.context.function,
                "selectors": dict(receipt.context.selectors),
            },
            "fs_ops": [self._fs_op_to_dict(op) for op in receipt.fs_ops],
            "policy_decisions": [
                {
                    "path": str(decision.path),
                    "action": decision.action,
                    "policy": decision.policy,
                    "result": decision.result,
                    "message": decision.message,
                }
                for decision in receipt.policy_decisions
            ],
            "hooks": [
                {
                    "name": log.name,
                    "path": str(log.path) if log.path else None,
                    "status": log.status,
                    "error": log.error,
                }
                for log in receipt.hooks
            ],
        }

    def _fs_op_to_dict(self, op: EnsureOp | MoveOp | WriteOp) -> dict[str, Any]:
        if isinstance(op, EnsureOp):
            return {
                "type": "ensure",
                "path": str(op.path),
                "metadata": dict(op.metadata),
            }
        if isinstance(op, MoveOp):
            return {
                "type": "move",
                "src": str(op.src),
                "dest": str(op.dest),
                "overwrite": op.overwrite,
                "metadata": dict(op.metadata),
            }
        if isinstance(op, WriteOp):
            return {
                "type": "write",
                "path": str(op.path),
                "event": op.event,
                "policy": op.policy,
                "doc_type": op.doc_type,
                "content_hash": op.content_hash,
                "metadata": dict(op.metadata),
                "hook_metadata": dict(op.hook_metadata),
                "timestamp": self._isoformat(op.timestamp) if op.timestamp else None,
            }
        raise TypeError(f"Unknown filesystem operation {type(op)!r}")

    def _receipt_to_journal(self, receipt_dict: Mapping[str, Any]) -> dict[str, Any]:
        context = receipt_dict.get("context") or {}
        fs_ops = receipt_dict.get("fs_ops") or []
        writes = [
            op for op in fs_ops if isinstance(op, Mapping) and op.get("type") == "write"
        ]
        moves = [
            op for op in fs_ops if isinstance(op, Mapping) and op.get("type") == "move"
        ]
        return {
            "action": "apply-plan",
            "object_type": context.get("object_type"),
            "function": context.get("function"),
            "selectors": dict(context.get("selectors") or {}),
            "writes": [
                {
                    key: value
                    for key, value in write.items()
                    if key in {"path", "event", "doc_type", "policy"}
                }
                for write in writes
                if isinstance(write, Mapping)
            ],
            "moves": [
                {
                    key: value
                    for key, value in move.items()
                    if key in {"src", "dest", "overwrite"}
                }
                for move in moves
                if isinstance(move, Mapping)
            ],
            "timestamp": receipt_dict.get("timestamp"),
        }

    def _merge_session_records(
        self,
        receipts: MutableMapping[int, dict[str, Any]] | list[dict[str, Any]],
        journal: MutableMapping[int, dict[str, Any]] | list[dict[str, Any]],
        session_dump: Mapping[str, Any],
    ) -> None:
        receipt_entries = self._coerce_record_list(session_dump.get("receipts"))
        if receipt_entries:
            receipts.extend(receipt_entries)  # type: ignore[arg-type]

        journal_entries = self._coerce_record_list(session_dump.get("journal"))
        if journal_entries:
            journal.extend(journal_entries)  # type: ignore[arg-type]

    def _coerce_record_list(self, value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, list):
            return [dict(item) if isinstance(item, Mapping) else {"value": item} for item in value]
        if isinstance(value, Mapping):
            return [dict(value)]
        return [{"value": value}]

    def _isoformat(self, dt: datetime) -> str:
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "FunctionCallRequest",
    "FunctionCallResult",
    "ObjectExecutor",
    "HandlerResolutionError",
]
