"""Environment implementations (kernel, etc.)."""

from .kernel.registry import get_environment as get_kernel_environment

__all__ = ["get_kernel_environment"]
