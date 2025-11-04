"""Shared workflow schema and dispatcher used by release orchestration."""

from __future__ import annotations

from typing import Dict, Mapping, MutableMapping, Optional

import requests
from pydantic import BaseModel, Field, ValidationError
from requests import Response, Session
from requests.exceptions import RequestException

from ..secrets import SecretSpec, register_secret, resolve_secret_info


class WorkflowTriggerError(RuntimeError):
    """Raised when a workflow dispatch cannot be completed."""


class WorkflowInputSpec(BaseModel):
    """Describes a single workflow input parameter."""

    description: Optional[str] = None
    default: Optional[str] = None
    required: bool = False


class WorkflowSpec(BaseModel):
    """Workflow metadata used to dispatch a GitHub Actions workflow."""

    slug: str
    repo: str
    workflow: str
    ref: str = "main"
    token_env: str = "GH_TOKEN_RELEASE"
    description: Optional[str] = None
    dry_run_supported: bool = True
    inputs: Dict[str, WorkflowInputSpec] = Field(default_factory=dict)

    def model_post_init(self, __context: MutableMapping[str, object]) -> None:  # type: ignore[override]
        register_secret(SecretSpec(name=self.token_env, description=f"Token for workflow '{self.slug}'"))
        super().model_post_init(__context)


class WorkflowDispatchResult(BaseModel):
    """Normalized response payload returned after attempting to dispatch."""

    status: str
    repo: str
    workflow: str
    ref: str
    inputs: Dict[str, str] = Field(default_factory=dict)
    dry_run: bool = False
    response_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None


def trigger_workflow(
    spec: WorkflowSpec,
    *,
    ref: Optional[str] = None,
    inputs: Optional[Mapping[str, str]] = None,
    token_env_override: Optional[str] = None,
    dry_run: bool = False,
    github_api: str = "https://api.github.com",
    session: Optional[Session] = None,
) -> WorkflowDispatchResult:
    """Dispatch a GitHub Actions workflow based on the provided spec."""

    effective_ref = ref or spec.ref
    provided_inputs: Mapping[str, str] = inputs or {}

    resolved_inputs: Dict[str, str] = {}
    for name, input_spec in spec.inputs.items():
        if name in provided_inputs:
            resolved_inputs[name] = str(provided_inputs[name])
        elif input_spec.default is not None:
            resolved_inputs[name] = input_spec.default
        elif input_spec.required:
            raise WorkflowTriggerError(f"Missing required workflow input '{name}' for workflow '{spec.slug}'.")

    # Allow callers to provide additional inputs not declared in the spec.
    for name, value in provided_inputs.items():
        if name not in resolved_inputs:
            resolved_inputs[name] = str(value)

    if dry_run:
        if not spec.dry_run_supported:
            raise WorkflowTriggerError(f"Workflow '{spec.slug}' does not support dry-run mode.")
        return WorkflowDispatchResult(
            status="skipped",
            repo=spec.repo,
            workflow=spec.workflow,
            ref=effective_ref,
            inputs=resolved_inputs,
            dry_run=True,
        )

    token_env = token_env_override or spec.token_env
    info = resolve_secret_info(token_env)
    token = info.value
    if not token:
        attempted = []
        for attempt in info.attempts:
            label = attempt.source or attempt.resolver
            path = attempt.details.get("path") if attempt.details else None
            if path:
                label = f"{label}@{path}"
            status = "resolved" if attempt.success else "missing"
            attempted.append(f"{label} ({status})")
        attempted_summary = ", ".join(attempted) if attempted else "none"
        raise WorkflowTriggerError(
            f"GitHub token environment variable '{token_env}' not resolved for workflow '{spec.slug}'. "
            f"Checked resolvers: {attempted_summary}. Run `aware-cli release secrets-list` for details."
        )

    request_session = session or requests.Session()
    url = f"{github_api.rstrip('/')}/repos/{spec.repo}/actions/workflows/{spec.workflow}/dispatches"
    payload = {"ref": effective_ref}
    if resolved_inputs:
        payload["inputs"] = resolved_inputs

    try:
        response: Response = request_session.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json=payload,
            timeout=20,
        )
    except RequestException as exc:
        raise WorkflowTriggerError(f"Workflow dispatch failed: {exc}") from exc

    if response.status_code not in (201, 204):
        raise WorkflowTriggerError(
            f"Workflow dispatch returned {response.status_code}: {response.text or response.reason}"
        )

    return WorkflowDispatchResult(
        status="dispatched",
        repo=spec.repo,
        workflow=spec.workflow,
        ref=effective_ref,
        inputs=resolved_inputs,
        dry_run=False,
        response_status=response.status_code,
        response_headers=dict(response.headers),
    )


__all__ = [
    "WorkflowDispatchResult",
    "WorkflowInputSpec",
    "WorkflowSpec",
    "WorkflowTriggerError",
    "trigger_workflow",
]
