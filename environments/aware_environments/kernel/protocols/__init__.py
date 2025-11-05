"""Kernel protocol exports."""

from pathlib import Path

from aware_environment import ProtocolSpec, ProtocolTarget

CURRENT = Path(__file__).parent / "current"

PROTOCOLS = (
    ProtocolSpec(
        id="protocol-thread-apt-binding",
        slug="thread-apt-binding",
        title="Thread-APT Binding Protocol",
        path=(CURRENT / "thread-apt-binding.md").resolve(),
        summary="Bind Agent Process Thread participants to orchestrator threads for visibility and receipts.",
        version="0.1",
        targets=(
            ProtocolTarget(object_type="thread", functions=("participants-bind", "participants-list")),
            ProtocolTarget(object_type="agent", functions=("whoami",)),
        ),
        metadata={"depends_on": ("apt-bootstrap",)},
    ),
    ProtocolSpec(
        id="protocol-apt-bootstrap",
        slug="apt-bootstrap",
        title="APT Bootstrap Protocol",
        path=(CURRENT / "apt-bootstrap.md").resolve(),
        summary="Guidance for establishing an Agent Process Thread when identity context is unknown.",
        version="0.1",
        targets=(
            ProtocolTarget(object_type="agent"),
            ProtocolTarget(object_type="agent-thread", functions=("login", "session-update")),
            ProtocolTarget(object_type="environment", functions=("render-guide",)),
        ),
    ),
)

__all__ = ["PROTOCOLS"]
