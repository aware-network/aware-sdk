"""Exception types used by the environment registries."""

from __future__ import annotations


class RegistryError(Exception):
    """Base error raised by environment registries."""


class EnvironmentLoadError(RegistryError):
    """Raised when an environment cannot be loaded from a module path."""


class DuplicateSpecError(RegistryError):
    """Raised when attempting to register a spec with an existing identifier."""


class UnknownSpecError(RegistryError):
    """Raised when requesting a spec that has not been registered."""


class PathSpecResolutionError(RegistryError):
    """Raised when a PathSpec cannot be resolved with the provided selectors."""


class AwareEnvironmentError(Exception):
    """Base error for runtime execution issues."""
