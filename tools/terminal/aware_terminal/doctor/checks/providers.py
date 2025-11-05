from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import List, Optional, Sequence

from aware_terminal.doctor.context import DoctorContext
from aware_terminal.doctor.models import (
    DoctorCheckResult,
    DoctorMessage,
    DoctorMessageLevel,
    DoctorRemediation,
    DoctorStatus,
    ProviderAction,
    ProviderActionStatus,
    combine_status,
)
from aware_terminal.providers import get_registry, list_providers


INSTALL_TOPLINE_COMMAND = ["aware-cli", "terminal", "providers", "install"]


@dataclass(slots=True)
class ProviderMetadata:
    package: Optional[str]
    binary_name: Optional[str]
    version_args: Sequence[str]
    summary: Optional[str]
    auto_install_env: Optional[str]
    docs_url: Optional[str]
    supported_version: Optional[str]


def _load_metadata(provider_module: str) -> ProviderMetadata:
    base_module = provider_module.rsplit(".", 1)[0]
    try:
        metadata_module = importlib.import_module(f"{base_module}.metadata")
    except ModuleNotFoundError:
        return ProviderMetadata(None, None, ("--version",), None, None, None)

    package = getattr(metadata_module, "PACKAGE_NAME", None)
    binary_name = getattr(metadata_module, "BINARY_NAME", None)
    version_args = getattr(metadata_module, "VERSION_ARGS", ("--version",))
    summary = getattr(metadata_module, "SUMMARY", None)
    auto_env = getattr(metadata_module, "AUTO_INSTALL_ENV", None)
    docs_url = getattr(metadata_module, "DOCS_URL", None)
    supported_version = getattr(metadata_module, "SUPPORTED_VERSION", None)
    return ProviderMetadata(package, binary_name, tuple(version_args), summary, auto_env, docs_url, supported_version)


def run_provider_check(context: DoctorContext) -> tuple[DoctorCheckResult, List[ProviderAction]]:
    # Ensure providers are registered via helper (imports provider bundle)
    list_providers()
    provider_objects = list(get_registry().list())

    messages: List[DoctorMessage] = []
    remediations: List[DoctorRemediation] = []
    provider_actions: List[ProviderAction] = []

    installed_count = 0
    pending_count = 0
    missing_count = 0
    status = DoctorStatus.OK

    if not provider_objects:
        status = DoctorStatus.ERROR
        summary = "No terminal providers registered."
        messages.append(
            DoctorMessage(
                level=DoctorMessageLevel.ERROR,
                text="Provider registry empty. Ensure aware-terminal providers package is installed.",
            )
        )
        remediations.append(
            DoctorRemediation(
                summary="Install provider bundle",
                command=["uv", "run", "pip", "install", "aware-terminal-providers"],
            )
        )
        check = DoctorCheckResult(
            slug="providers",
            title="Agent Providers",
            status=status,
            summary=summary,
            messages=messages,
            remediations=remediations,
            data={"providers": []},
        )
        return check, provider_actions

    update_count = 0

    for provider in provider_objects:
        meta = _load_metadata(provider.__class__.__module__)
        install_command = INSTALL_TOPLINE_COMMAND + [provider.info.slug]
        fallback_command = (
            ["npm", "install", "-g", meta.package] if meta.package else None
        )

        install_status = None
        if hasattr(provider, "evaluate_installation"):
            try:
                install_status = provider.evaluate_installation()  # type: ignore[attr-defined]
            except Exception:
                install_status = None

        installed_version = install_status.version if install_status else None
        binary_path = install_status.binary_path if (install_status and install_status.binary_path) else None
        provider_status = ProviderActionStatus.PENDING
        summary = meta.summary or provider.info.description or provider.info.title
        message_level = DoctorMessageLevel.INFO
        message_text = ""
        latest_version = meta.supported_version

        if install_status and install_status.success and binary_path:
            provider_status = ProviderActionStatus.INSTALLED
            installed_count += 1
            message_level = DoctorMessageLevel.SUCCESS
            version_note = f" ({installed_version})" if installed_version else ""
            message_text = f"{provider.info.title} CLI '{meta.binary_name or provider.info.slug}' installed{version_note}"
            if latest_version and installed_version and not _version_matches(installed_version, latest_version):
                provider_status = ProviderActionStatus.UPDATE_AVAILABLE
                update_count += 1
                status = combine_status(status, DoctorStatus.WARNING)
                message_level = DoctorMessageLevel.WARNING
                message_text = (
                    f"{provider.info.title} installed {installed_version}; latest supported {latest_version}."
                )
                remediations.append(
                    DoctorRemediation(
                        summary=f"Update {provider.info.title}",
                        command=install_command,
                        docs_url=meta.docs_url,
                    )
                )
        elif install_status and not install_status.success:
            provider_status = ProviderActionStatus.MISSING
            missing_count += 1
            status = combine_status(status, DoctorStatus.WARNING)
            message_level = DoctorMessageLevel.WARNING
            message_text = install_status.message or f"{provider.info.title} not installed."
            if install_status.command:
                fallback_command = list(install_status.command)
            remediations.append(
                DoctorRemediation(
                    summary=f"Install {provider.info.title}",
                    command=install_command,
                    docs_url=meta.docs_url,
                )
            )
        else:
            provider_status = ProviderActionStatus.PENDING
            pending_count += 1
            status = combine_status(status, DoctorStatus.WARNING)
            message_level = DoctorMessageLevel.WARNING
            message_text = (
                f"{provider.info.title} automation pending—track provider task for updates."
            )

        messages.append(DoctorMessage(level=message_level, text=message_text))
        provider_actions.append(
            ProviderAction(
                slug=provider.info.slug,
                title=provider.info.title,
                status=provider_status,
                summary=summary,
                cli_name=meta.binary_name,
                package=meta.package,
                install_command=install_command,
                fallback_command=fallback_command,
                installed_version=installed_version,
                latest_version=latest_version,
                docs_url=meta.docs_url,
                auto_install_env=meta.auto_install_env,
            )
        )

    summary_parts = [
        f"{installed_count} installed",
        f"{missing_count} missing",
        f"{pending_count} pending",
        f"{update_count} updates" if update_count else None,
    ]
    summary = ", ".join(part for part in summary_parts if part)

    check = DoctorCheckResult(
        slug="providers",
        title="Agent Providers",
        status=status,
        summary=summary,
        blocking=missing_count > 0,
        messages=messages,
        remediations=remediations,
        data={
            "installed": installed_count,
            "missing": missing_count,
            "pending": pending_count,
        },
    )
    return check, provider_actions
def _version_matches(installed: Optional[str], latest: Optional[str]) -> bool:
    if not installed or not latest:
        return False
    installed_clean = installed.strip().lower()
    latest_clean = latest.strip().lower()
    return installed_clean == latest_clean or installed_clean.endswith(latest_clean)
