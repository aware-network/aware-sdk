"""Release helpers exposed by the kernel."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "bundle",
    "publish",
    "locks_generate",
    "manifest_validate",
    "terminal_refresh",
    "terminal_validate",
    "workflow_trigger",
    "secrets_list",
    "ReleaseBundleArtifact",
    "ReleasePublishOutcome",
    "ReleaseLockArtifact",
    "ReleaseManifestModel",
    "ReleaseManifestValidation",
    "ReleaseChecksumModel",
    "ReleaseProviderInfoModel",
    "ReleaseBundlePlanResult",
    "ReleaseLockPlanResult",
    "ReleasePublishPlanResult",
    "ReleaseTerminalRefreshPlanResult",
    "plan_bundle",
    "plan_publish",
    "plan_generate_lock",
]


_HANDLER_EXPORTS = {
    "bundle",
    "publish",
    "locks_generate",
    "manifest_validate",
    "terminal_refresh",
    "terminal_validate",
    "workflow_trigger",
    "secrets_list",
    "ReleaseTerminalRefreshPlanResult",
}
_PLAN_EXPORTS = {
    "ReleaseBundlePlanResult",
    "ReleaseLockPlanResult",
    "ReleasePublishPlanResult",
    "plan_bundle",
    "plan_publish",
    "plan_generate_lock",
}
_MODEL_EXPORTS = {
    "ReleaseBundleArtifact",
    "ReleaseLockArtifact",
    "ReleasePublishOutcome",
    "ReleaseManifestModel",
    "ReleaseManifestValidation",
    "ReleaseChecksumModel",
    "ReleaseProviderInfoModel",
}


def __getattr__(name: str) -> Any:  # pragma: no cover - simple import shim
    if name in _HANDLER_EXPORTS:
        module = import_module(".handlers", __name__)
        value = getattr(module, name)
    elif name in _PLAN_EXPORTS:
        module = import_module(".write_plan", __name__)
        value = getattr(module, name)
    elif name in _MODEL_EXPORTS:
        module = import_module(".models", __name__)
        value = getattr(module, name)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value
