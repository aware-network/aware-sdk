"""Release tooling helpers for aware-cli bundles."""

__version__ = "0.1.2"
from .bundle.builder import BundleBuilder, BundleConfig
from .schemas.release import BundleManifest, ReleaseIndex
from .publish import PublishContext, PublishResult, UploadResult, publish_bundle
from .secrets import (
    SecretAttempt,
    SecretResolutionInfo,
    describe_secret,
    list_secrets,
    register_resolver,
    register_secret,
    resolve_secret,
    resolve_secret_info,
    use_dotenv,
)
from .workflows import (
    WorkflowDispatchResult,
    WorkflowInputSpec,
    WorkflowSpec,
    WorkflowTriggerError,
    trigger_workflow,
)

__all__ = [
    "__version__",
    "BundleConfig",
    "BundleBuilder",
    "BundleManifest",
    "ReleaseIndex",
    "PublishContext",
    "PublishResult",
    "UploadResult",
    "publish_bundle",
    "SecretAttempt",
    "SecretResolutionInfo",
    "list_secrets",
    "describe_secret",
    "register_resolver",
    "register_secret",
    "resolve_secret",
    "resolve_secret_info",
    "use_dotenv",
    "WorkflowDispatchResult",
    "WorkflowInputSpec",
    "WorkflowSpec",
    "WorkflowTriggerError",
    "trigger_workflow",
]
