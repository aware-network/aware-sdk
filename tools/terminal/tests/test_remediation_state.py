from aware_terminal.remediation.models import (
    RemediationOutcome,
    RemediationStatus,
    SetupState,
)


def test_setup_state_record_overwrites_previous_entry():
    state = SetupState()
    first = RemediationOutcome(
        action_id="tmux_service",
        summary="tmux",
        status=RemediationStatus.EXECUTED,
    )
    second = RemediationOutcome(
        action_id="tmux_service",
        summary="tmux",
        status=RemediationStatus.MANUAL,
        message="needs systemd",
        command=["systemctl", "--user", "enable", "--now", "tmux.service"],
    )

    state.record(first)
    assert len(state.runs) == 1
    state.record(second)
    assert len(state.runs) == 1
    entry = state.last_status("tmux_service")
    assert entry is not None
    assert entry.status == RemediationStatus.MANUAL
    assert entry.details["message"] == "needs systemd"
    assert entry.details["command"] == ["systemctl", "--user", "enable", "--now", "tmux.service"]
