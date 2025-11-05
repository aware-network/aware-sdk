"""Runtime filesystem adapters (legacy shim).

The canonical implementations live in
``aware_environments.kernel.objects``. This package re-exports the
kernel symbols so historical imports continue to resolve while CLI migrations
complete.
"""

from aware_environments.kernel.objects._shared.runtime_models import (  # type: ignore[import]
    RuntimeEvent,
)
from aware_environments.kernel.objects._shared.fs_utils import (  # type: ignore[import]
    ensure_iso_timestamp,
    write_json_atomic,
)
from aware_environments.kernel.objects.process.schemas import ProcessEntry  # type: ignore[import]
from aware_environments.kernel.objects.process.fs import ProcessFSAdapter  # type: ignore[import]
from aware_environments.kernel.objects.process.handlers import (  # type: ignore[import]
    list_processes,
    process_backlog,
    process_status,
    process_threads,
)
from aware_environments.kernel.objects.thread.schemas import (  # type: ignore[import]
    ThreadEntry,
    ThreadParticipant,
    ThreadParticipantIdentity,
    ThreadParticipantIdentityAgent,
    ThreadParticipantIdentityHuman,
    ThreadParticipantIdentityOrganization,
    ThreadParticipantIdentityService,
    ThreadParticipantRole,
    ThreadParticipantSession,
    ThreadParticipantSessionState,
    ThreadParticipantStatus,
    ThreadParticipantType,
    ThreadParticipantsManifest,
)
from aware_environments.kernel.objects.thread.fs import ThreadFSAdapter  # type: ignore[import]
from aware_environments.kernel.objects.thread.handlers import (  # type: ignore[import]
    list_threads,
    thread_activity,
    thread_branches,
    thread_conversations,
    thread_status,
)

from .executor import (
    FunctionCallRequest,
    FunctionCallResult,
    HandlerResolutionError,
    ObjectExecutor,
)
from .function_call_request_builder import (
    ArgumentResolver,
    build_function_call_request,
    build_session_config,
    normalize_executor_payload,
    SelectorResolver,
    SessionResolver,
)

__all__ = [
    "RuntimeEvent",
    "ProcessEntry",
    "ThreadEntry",
    "ThreadParticipant",
    "ThreadParticipantIdentity",
    "ThreadParticipantIdentityAgent",
    "ThreadParticipantIdentityHuman",
    "ThreadParticipantIdentityOrganization",
    "ThreadParticipantIdentityService",
    "ThreadParticipantRole",
    "ThreadParticipantSession",
    "ThreadParticipantSessionState",
    "ThreadParticipantStatus",
    "ThreadParticipantType",
    "ThreadParticipantsManifest",
    "ProcessFSAdapter",
    "ThreadFSAdapter",
    "ensure_iso_timestamp",
    "write_json_atomic",
    "list_processes",
    "process_status",
    "process_threads",
    "process_backlog",
    "list_threads",
    "thread_status",
    "thread_activity",
    "thread_branches",
    "thread_conversations",
    "ObjectExecutor",
    "FunctionCallRequest",
    "FunctionCallResult",
    "HandlerResolutionError",
    "build_function_call_request",
    "build_session_config",
    "normalize_executor_payload",
    "SelectorResolver",
    "ArgumentResolver",
    "SessionResolver",
]
