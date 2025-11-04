"""High-level publish workflow."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

from ..bundle.utils import compute_sha256, write_text
from ..schemas.release import BundleManifest
from .adapters import build_adapter
from .index import load_release_index, update_release_index
from .models import PublishContext, PublishResult, UploadResult


def publish_bundle(context: PublishContext) -> PublishResult:
    logs = []
    manifest = context.manifest

    archive_checksum = compute_sha256(context.archive_path)
    checksum_match = archive_checksum == manifest.checksum.sha256
    if not checksum_match:
        raise ValueError(
            f"Archive checksum mismatch. Manifest={manifest.checksum.sha256} Archive={archive_checksum}"
        )

    adapter = build_adapter(
        context.adapter_name,
        command=context.adapter_options.get("command"),
        env={
            key[len("env.") :]: value
            for key, value in context.adapter_options.items()
            if key.startswith("env.")
        },
        options=context.adapter_options,
    )

    upload_result = UploadResult(
        adapter=adapter.name,
        status="skipped",
        url=context.url,
        logs=[],
        details={},
    )

    if context.dry_run:
        upload_result.logs.append("Dry run enabled; upload skipped.")
    else:
        upload_result = adapter.publish(context)

    logs.extend(upload_result.logs)

    signature_path: Optional[Path] = None
    if context.signature_command and not context.dry_run:
        signature_path = _run_signature_command(context.signature_command, context.archive_path, logs)

    index_path = context.releases_index_path
    index_updated = False
    if index_path:
        if context.dry_run:
            logs.append(f"Dry run: skipping release index update for {index_path}.")
        else:
            index = load_release_index(index_path)
            index = update_release_index(index, manifest, context.url, context.notes, signature_path)
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(index.model_dump_json(indent=2) + "\n", encoding="utf-8")
            logs.append(f"Updated releases index at {index_path}.")
            index_updated = True

    metadata: Dict[str, object] = {
        "published_at": context.published_at.isoformat() + "Z",
    }
    if context.actor:
        metadata["actor"] = context.actor

    next_steps = []
    if upload_result.status != "succeeded":
        next_steps.append("Upload bundle to distribution storage.")
    if not index_updated and index_path:
        next_steps.append(f"Update {index_path} with release entry once upload completes.")

    return PublishResult(
        manifest_path=context.manifest_path,
        archive_path=context.archive_path,
        checksum_match=True,
        index_path=index_path,
        index_updated=index_updated,
        signature_path=signature_path,
        upload=upload_result,
        logs=logs,
        next_steps=next_steps,
        metadata=metadata,
    )


def _run_signature_command(command: str, archive_path: Path, logs: list[str]) -> Optional[Path]:
    command = command.replace("{archive}", str(archive_path))
    proc = subprocess.run(
        command,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        logs.append(proc.stdout.strip())
    if proc.stderr:
        logs.append(proc.stderr.strip())
    if proc.returncode != 0:
        logs.append(f"Signature command failed (exit {proc.returncode}); continuing without signature.")
        return None
    candidate = Path(f"{archive_path}.sig")
    if candidate.exists():
        return candidate
    return None
