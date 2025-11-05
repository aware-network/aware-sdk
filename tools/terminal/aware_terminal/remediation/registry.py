from __future__ import annotations

import platform as py_platform
from typing import Iterable, Iterator, List, Sequence

from .models import (
    RemediationAction,
    RemediationContext,
    RemediationOutcome,
    RemediationPolicy,
    SetupState,
)

# Internal registry populated at import time.
_ACTION_FACTORIES: List[callable] = []


def register_action(factory) -> None:
    _ACTION_FACTORIES.append(factory)


def _default_platform() -> str:
    system = py_platform.system().lower()
    if system.startswith("linux"):
        return "linux"
    if system.startswith("darwin"):
        return "macos"
    if system.startswith("windows"):
        return "windows"
    return system


def build_context(
    *,
    config: ToolConfig,
    auto: bool,
    provider_policy: RemediationPolicy,
    state: SetupState | None = None,
    platform: str | None = None,
    interactive: bool = False,
) -> RemediationContext:
    plat = platform or _default_platform()
    return RemediationContext(
        config=config,
        auto=auto,
        platform=plat,
        provider_policy=provider_policy,
        state=state,
        interactive=interactive,
    )


def get_actions(context: RemediationContext) -> List[RemediationAction]:
    actions: List[RemediationAction] = []
    for factory in _ACTION_FACTORIES:
        produced = factory(context)
        if not produced:
            continue
        if isinstance(produced, RemediationAction):
            produced = [produced]
        for action in produced:
            if action and action.supports_platform(context.platform):
                actions.append(action)
    return actions


def iter_actions(context: RemediationContext) -> Iterator[RemediationAction]:
    for action in get_actions(context):
        yield action


def execute_actions(context: RemediationContext, renderer=None) -> List[RemediationOutcome]:
    outcomes: List[RemediationOutcome] = []
    for action in iter_actions(context):
        if renderer is not None:
            renderer.action_start(action.id, action.summary)
        outcome = action.run(context, renderer=renderer)
        outcomes.append(outcome)
        if renderer is not None:
            renderer.action_complete(
                outcome.action_id,
                outcome.status.value,
                outcome.message,
            )
        if context.state is not None and context.auto:
            context.state.record(outcome)
    return outcomes
