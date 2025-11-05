"""Kernel object exports."""

from .agent.spec import AGENT_OBJECT_SPEC
from .agent_thread.spec import AGENT_THREAD_OBJECT_SPEC
from .agent_thread_memory.spec import AGENT_THREAD_MEMORY_OBJECT_SPEC
from .conversation.spec import CONVERSATION_OBJECT_SPEC
from .environment.spec import ENVIRONMENT_OBJECT_SPEC
from .process.spec import PROCESS_OBJECT_SPEC
from .project.spec import PROJECT_OBJECT_SPEC
from .role.spec import ROLE_OBJECT_SPEC
from .rule.spec import RULE_OBJECT_SPEC
from .release.spec import RELEASE_OBJECT_SPEC
from .repository.spec import REPOSITORY_OBJECT_SPEC
from .task.spec import TASK_OBJECT_SPEC
from .terminal.spec import TERMINAL_OBJECT_SPEC
from .thread.spec import THREAD_OBJECT_SPEC

LEGACY_OBJECTS: tuple = ()

OBJECTS = (
    AGENT_OBJECT_SPEC,
    AGENT_THREAD_OBJECT_SPEC,
    AGENT_THREAD_MEMORY_OBJECT_SPEC,
    CONVERSATION_OBJECT_SPEC,
    ENVIRONMENT_OBJECT_SPEC,
    PROCESS_OBJECT_SPEC,
    ROLE_OBJECT_SPEC,
    RULE_OBJECT_SPEC,
    PROJECT_OBJECT_SPEC,
    RELEASE_OBJECT_SPEC,
    REPOSITORY_OBJECT_SPEC,
    TASK_OBJECT_SPEC,
    TERMINAL_OBJECT_SPEC,
    THREAD_OBJECT_SPEC,
    *LEGACY_OBJECTS,
)

__all__ = ["OBJECTS"]
