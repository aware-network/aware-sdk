"\"\"\"Shared helpers for terminal provider adapters.\"\"\""

from .provider_base import ProviderAdapter, ProviderMessage, ProviderContext
from .descriptor import load_provider_descriptor, save_provider_descriptor, ProviderDescriptor
from .version import get_supported_version, get_channel_info

__all__ = [
    "ProviderAdapter",
    "ProviderMessage",
    "ProviderContext",
    "ProviderDescriptor",
    "load_provider_descriptor",
    "save_provider_descriptor",
    "get_supported_version",
    "get_channel_info",
]
