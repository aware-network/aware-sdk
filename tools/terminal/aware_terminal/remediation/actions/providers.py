from __future__ import annotations

from typing import Iterable, List, Optional

from aware_terminal.providers import get_provider, list_providers, run_provider_action
from aware_terminal.providers.base import TerminalProvider
from aware_terminal_providers.core import get_channel_info

from ..models import (
    CapabilitySnapshot,
    RemediationAction,
    RemediationContext,
    RemediationOutcome,
    RemediationPolicy,
    RemediationStatus,
)


class ProviderRemediationAction(RemediationAction):
    blocking = False
    policy = RemediationPolicy.APPLY
    platforms = ()

    def __init__(
        self,
        context: RemediationContext,
        slug: str,
        title: str,
        provider: Optional[TerminalProvider],
    ):
        self.context = context
        self.slug = slug
        self.title = title
        self.id = f"provider:{slug}"
        self.summary = f"Provider {title}"
        self._provider = provider

    def capability(self, context: RemediationContext) -> CapabilitySnapshot:
        summary = f"Provider {self.title}"
        data = {
            "slug": self.slug,
            "title": self.title,
            "policy": context.provider_policy.value,
        }
        return CapabilitySnapshot(summary=summary, data=data)

    def run(
        self,
        context: RemediationContext,
        renderer=None,
    ) -> RemediationOutcome:
        command = [
            "aware-cli",
            "terminal",
            "providers",
            "install",
            self.slug,
        ]
        details = self._provider_details()
        needs_update = details.get("needs_update")
        if needs_update is None:
            latest = details.get("latest_version")
            installed = details.get("installed_version")
            needs_update = bool(latest and installed and str(installed) != str(latest))

        payload_details = {"provider": self.slug, **details}

        if renderer is not None:
            renderer.provider_prompt(self.slug, self.title, details)

        if not context.auto:
            status = RemediationStatus.MANUAL if needs_update else RemediationStatus.EXECUTED
            message = "Provider update available" if needs_update else "Already up to date."
            return RemediationOutcome(
                action_id=self.id,
                summary=self.summary,
                status=status,
                blocking=self.blocking,
                command=command if needs_update else None,
                message=message,
                details=payload_details,
            )

        if not needs_update:
            return RemediationOutcome(
                action_id=self.id,
                summary=self.summary,
                status=RemediationStatus.EXECUTED,
                blocking=self.blocking,
                command=None,
                message="Already up to date.",
                details=payload_details,
            )

        if context.provider_policy == RemediationPolicy.SKIP:
            if context.interactive and renderer is not None:
                prompt = f"Update provider {self.title}?"
                proceed = renderer.confirm_provider(prompt, default=False)
                if not proceed:
                    return RemediationOutcome(
                        action_id=self.id,
                        summary=self.summary,
                        status=RemediationStatus.MANUAL,
                        blocking=self.blocking,
                        command=command,
                        message="Provider update skipped",
                        details=payload_details,
                    )
            else:
                return RemediationOutcome(
                    action_id=self.id,
                    summary=self.summary,
                    status=RemediationStatus.MANUAL,
                    blocking=self.blocking,
                    command=command,
                    message="Provider update skipped",
                    details=payload_details,
                )

        result = run_provider_action(self.slug, "install")
        if result is None:
            return RemediationOutcome(
                action_id=self.id,
                summary=self.summary,
                status=RemediationStatus.FAILED,
                blocking=self.blocking,
                command=command,
                message="Provider not registered",
                details=payload_details,
            )

        success = getattr(result, "success", False)
        message = getattr(result, "message", "")
        data = getattr(result, "data", {}) or {}
        status = RemediationStatus.EXECUTED if success else RemediationStatus.MANUAL
        combined_details = {"provider": self.slug, "result": data, **details}
        return RemediationOutcome(
            action_id=self.id,
            summary=self.summary,
            status=status,
            blocking=self.blocking,
            command=None if success else command,
            message=message or None,
            details=combined_details,
        )

    def _provider_details(self) -> dict:
        details: dict = {}
        try:
            info = get_channel_info(self.slug, channel="latest")
        except Exception:
            info = None
        latest_version = None
        if info is not None:
            latest_version = info.version
            details["latest_version"] = latest_version
            details["latest_updated_at"] = info.updated_at
            release_notes = info.release_notes or {}
            if isinstance(release_notes, dict):
                summary = release_notes.get("summary")
                url = release_notes.get("url")
                if summary:
                    details["release_summary"] = summary
                if url:
                    details["release_url"] = url
        installed_version = None
        if self._provider is not None and hasattr(self._provider, "evaluate_installation"):
            try:
                status = self._provider.evaluate_installation()  # type: ignore[attr-defined]
            except Exception:
                status = None
            if status and getattr(status, "version", None):
                installed_version = status.version
        if installed_version:
            details["installed_version"] = installed_version

        if latest_version and installed_version:
            details["needs_update"] = str(installed_version) != str(latest_version)
        elif latest_version and not installed_version:
            details["needs_update"] = True
        else:
            details["needs_update"] = False
        return details


def provider_actions_factory(context: RemediationContext) -> List[RemediationAction]:
    providers = list(list_providers())
    actions: List[RemediationAction] = []
    for info in providers:
        provider_obj = get_provider(info.slug)
        actions.append(ProviderRemediationAction(context, info.slug, info.title, provider_obj))
    return actions
