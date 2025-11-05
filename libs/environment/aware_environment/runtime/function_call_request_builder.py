"""Utilities to build FunctionCallRequest instances for callers."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional, Protocol, Tuple

from ..environment import Environment
from ..exceptions import UnknownSpecError
from ..object.spec import ObjectFunctionSpec, ObjectSpec
from .executor import FunctionCallRequest, FunctionCallResult

Selectors = Mapping[str, Any]
Arguments = Mapping[str, Any]
OptionsMapping = Mapping[str, Any]


class SelectorResolver(Protocol):
    """Resolve selectors for the function call."""

    def __call__(
        self,
        *,
        options: OptionsMapping,
        object_spec: ObjectSpec,
        function_spec: ObjectFunctionSpec,
    ) -> Selectors:
        ...


class ArgumentResolver(Protocol):
    """Resolve arguments for the function call."""

    def __call__(
        self,
        *,
        options: OptionsMapping,
        object_spec: ObjectSpec,
        function_spec: ObjectFunctionSpec,
    ) -> Arguments:
        ...


class SessionResolver(Protocol):
    """Resolve session configuration for the function call."""

    def __call__(
        self,
        *,
        options: OptionsMapping,
        selectors: Selectors,
        object_spec: ObjectSpec,
        function_spec: ObjectFunctionSpec,
    ) -> Any | None:
        ...


DEFAULT_SELECTOR_KEY = "selectors"
DEFAULT_ARGUMENTS_KEY = "arguments"
DEFAULT_SESSION_CONFIG_KEY = "session_config"


def _normalise_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): entry for key, entry in value.items()}


def _metadata_selectors(function_spec: ObjectFunctionSpec) -> Tuple[str, ...]:
    metadata = function_spec.metadata or {}
    selectors = metadata.get("selectors")
    if selectors is None:
        return tuple()
    if isinstance(selectors, str):
        return (selectors,)
    if isinstance(selectors, (list, tuple, set)):
        return tuple(str(item) for item in selectors)
    return tuple()


def default_selector_resolver(
    *,
    options: OptionsMapping,
    object_spec: ObjectSpec,
    function_spec: ObjectFunctionSpec,
) -> Selectors:
    selectors_opt = options.get(DEFAULT_SELECTOR_KEY)
    if isinstance(selectors_opt, Mapping):
        return _normalise_mapping(selectors_opt)

    resolved: dict[str, Any] = {}
    expected = _metadata_selectors(function_spec)
    for selector in expected:
        if selector in options:
            resolved[selector] = options[selector]
        else:
            raise ValueError(
                f"Selector '{selector}' is required for {object_spec.type}.{function_spec.name}."
            )
    return resolved


def default_argument_resolver(
    *,
    options: OptionsMapping,
    object_spec: ObjectSpec,
    function_spec: ObjectFunctionSpec,
) -> Arguments:
    arguments_opt = options.get(DEFAULT_ARGUMENTS_KEY)
    if isinstance(arguments_opt, Mapping):
        return dict(arguments_opt)
    return {}


def default_session_resolver(
    *,
    options: OptionsMapping,
    selectors: Selectors,
    object_spec: ObjectSpec,
    function_spec: ObjectFunctionSpec,
) -> Any | None:
    session_opt = options.get(DEFAULT_SESSION_CONFIG_KEY)
    if session_opt is not None:
        return session_opt
    return None


def _resolve_specs(environment: Environment, object_type: str, function_name: str) -> Tuple[ObjectSpec, ObjectFunctionSpec]:
    try:
        object_spec = environment.objects.get(object_type)
    except UnknownSpecError as exc:  # pragma: no cover - defensive
        raise exc

    for function_spec in object_spec.functions:
        if function_spec.name == function_name:
            return object_spec, function_spec
    raise UnknownSpecError(f"Function '{function_name}' not registered for object '{object_type}'.")


def build_function_call_request(
    *,
    environment: Environment,
    object_type: str,
    function_name: str,
    options: OptionsMapping,
    selector_resolver: SelectorResolver | None = None,
    argument_resolver: ArgumentResolver | None = None,
    session_resolver: SessionResolver | None = None,
) -> tuple[FunctionCallRequest, Any | None]:
    object_spec, function_spec = _resolve_specs(environment, object_type, function_name)

    selector_resolver = selector_resolver or default_selector_resolver
    argument_resolver = argument_resolver or default_argument_resolver
    session_resolver = session_resolver or default_session_resolver

    selectors = selector_resolver(
        options=options,
        object_spec=object_spec,
        function_spec=function_spec,
    )

    arguments = argument_resolver(
        options=options,
        object_spec=object_spec,
        function_spec=function_spec,
    )

    session_config = session_resolver(
        options=options,
        selectors=selectors,
        object_spec=object_spec,
        function_spec=function_spec,
    )

    request = FunctionCallRequest(
        object_type=object_spec.type,
        function_name=function_spec.name,
        selectors=dict(selectors),
        arguments=dict(arguments),
        session_config=session_config,
    )
    return request, session_config


def build_session_config(
    *,
    options: OptionsMapping,
    selectors: Selectors,
    resolver: SessionResolver | None = None,
    object_spec: ObjectSpec,
    function_spec: ObjectFunctionSpec,
) -> Any | None:
    session_resolver = resolver or default_session_resolver
    return session_resolver(
        options=options,
        selectors=selectors,
        object_spec=object_spec,
        function_spec=function_spec,
    )


def normalize_executor_payload(
    result: FunctionCallResult,
    *,
    flatten_payload: bool = True,
    include_selectors: bool = True,
) -> dict[str, Any]:
    if flatten_payload:
        if isinstance(result.payload, Mapping):
            payload: MutableMapping[str, Any] = dict(result.payload)
        elif result.payload is None:
            payload = {}
        else:
            payload = {"value": result.payload}
    else:
        payload = {"payload": result.payload}

    if result.receipts:
        payload.setdefault("receipts", result.receipts)
    if result.journal:
        payload.setdefault("journal", result.journal)
    if result.rule_ids:
        payload.setdefault("rule_ids", list(result.rule_ids))
    if include_selectors and "selectors" not in payload:
        payload["selectors"] = dict(result.selectors)
    if result.warnings:
        payload.setdefault("warnings", list(result.warnings))
    return dict(payload)


__all__ = [
    "build_function_call_request",
    "build_session_config",
    "normalize_executor_payload",
    "SelectorResolver",
    "ArgumentResolver",
    "SessionResolver",
]
