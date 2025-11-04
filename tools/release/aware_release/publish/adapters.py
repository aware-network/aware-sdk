"""Storage adapters used during publish."""

from __future__ import annotations

import shlex
import subprocess
from abc import ABC, abstractmethod
import os
import shlex
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Iterable, Optional

from .models import PublishContext, UploadResult


class StorageAdapter(ABC):
    name: str

    @abstractmethod
    def publish(self, context: PublishContext) -> UploadResult:
        ...


class NoOpAdapter(StorageAdapter):
    name = "noop"

    def publish(self, context: PublishContext) -> UploadResult:
        logs = [
            "NoOp adapter selected; skipping upload.",
            f"Bundle ready at {context.archive_path}",
        ]
        if context.url:
            logs.append(f"Target URL (manual upload): {context.url}")
        return UploadResult(
            adapter=self.name,
            status="skipped",
            url=context.url,
            logs=logs,
            details={},
        )


class CommandAdapter(StorageAdapter):
    name = "command"

    def __init__(self, command: str, env: Optional[Dict[str, str]] = None) -> None:
        self.command = command
        self.env = env or {}

    def publish(self, context: PublishContext) -> UploadResult:
        cmd = self._render_command(context)
        env = {**self.env}
        logs = [f"Executing upload command: {cmd}"]
        proc = subprocess.run(
            cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            env={**env, **_build_env(context)},
        )
        if proc.stdout:
            logs.append(proc.stdout.strip())
        if proc.stderr:
            logs.append(proc.stderr.strip())
        status = "succeeded" if proc.returncode == 0 else "failed"
        details = {"returncode": proc.returncode}
        return UploadResult(
            adapter=self.name,
            status=status,
            url=context.url,
            logs=logs,
            details=details,
        )

    def _render_command(self, context: PublishContext) -> str:
        replacements = {
            "{manifest}": shlex.quote(str(context.manifest_path)),
            "{archive}": shlex.quote(str(context.archive_path)),
            "{channel}": shlex.quote(context.manifest.channel),
            "{version}": shlex.quote(context.manifest.version),
            "{url}": shlex.quote(context.url or ""),
        }
        command = self.command
        for placeholder, value in replacements.items():
            command = command.replace(placeholder, value)
        return command


def _build_env(context: PublishContext) -> Dict[str, str]:
    env: Dict[str, str] = {
        "AWARE_RELEASE_CHANNEL": context.manifest.channel,
        "AWARE_RELEASE_VERSION": context.manifest.version,
        "AWARE_RELEASE_ARCHIVE": str(context.archive_path),
        "AWARE_RELEASE_MANIFEST": str(context.manifest_path),
    }
    if context.url:
        env["AWARE_RELEASE_URL"] = context.url
    if context.notes:
        env["AWARE_RELEASE_NOTES"] = context.notes
    return env


class GitHubReleasesAdapter(StorageAdapter):
    name = "github"

    def __init__(self, repo: str, token_env: str = "GITHUB_TOKEN", tag: Optional[str] = None, release_name: Optional[str] = None, prerelease: bool = False) -> None:
        self.repo = repo
        self.token_env = token_env
        self.tag = tag
        self.release_name = release_name
        self.prerelease = prerelease

    def publish(self, context: PublishContext) -> UploadResult:
        token = os.getenv(self.token_env)
        if not token:
            return UploadResult(
                adapter=self.name,
                status="failed",
                url=None,
                logs=[f"GitHub token environment variable '{self.token_env}' is not set."],
                details={},
            )

        tag = self.tag or f"aware-cli/{context.manifest.channel}/{context.manifest.version}"
        base_command = [
            "gh",
            "release",
            "upload",
            tag,
            str(context.archive_path),
            "--repo",
            self.repo,
            "--clobber",
        ]
        env = {"GH_TOKEN": token}
        logs = [f"Uploading archive to GitHub release {self.repo}@{tag} via gh CLI."]

        proc = subprocess.run(
            base_command,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.stdout:
            logs.append(proc.stdout.strip())
        if proc.stderr:
            logs.append(proc.stderr.strip())
        if proc.returncode != 0:
            return UploadResult(
                adapter=self.name,
                status="failed",
                url=None,
                logs=logs,
                details={"returncode": proc.returncode},
            )

        release_url = f"https://github.com/{self.repo}/releases/tag/{tag}"
        asset_url = context.url or release_url
        return UploadResult(
            adapter=self.name,
            status="succeeded",
            url=asset_url,
            logs=logs,
            details={"release": release_url},
        )
def build_adapter(
    name: str,
    *,
    command: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    options: Optional[Dict[str, object]] = None,
) -> StorageAdapter:
    lowered = (name or "noop").lower()
    if lowered in ("noop", "none"):
        return NoOpAdapter()
    if lowered in ("cmd", "command") and command:
        return CommandAdapter(command=command, env=env)
    if lowered in ("github", "gh"):
        opts = options or {}
        repo = str(opts.get("repo")) if opts.get("repo") else None
        if not repo:
            raise ValueError("GitHub adapter requires adapter-arg repo=owner/name")
        return GitHubReleasesAdapter(
            repo=repo,
            token_env=str(opts.get("token-env", "GITHUB_TOKEN")),
            tag=opts.get("tag"),
            release_name=opts.get("release-name"),
            prerelease=str(opts.get("prerelease", "false")).lower() == "true",
        )
    if lowered == "s3":
        opts = options or {}
        bucket = opts.get("bucket")
        path_tpl = opts.get("path")
        if not bucket or not path_tpl:
            raise ValueError("S3 adapter requires adapter-arg bucket=... and path=...")
        return S3Adapter(
            bucket=str(bucket),
            path_template=str(path_tpl),
            region=str(opts.get("region")) if opts.get("region") else None,
            profile=str(opts.get("profile")) if opts.get("profile") else None,
            public_url=str(opts.get("public-url")) if opts.get("public-url") else None,
        )
    raise ValueError(f"Unknown publish adapter '{name}'")
class S3Adapter(StorageAdapter):
    name = "s3"

    def __init__(self, bucket: str, path_template: str, region: Optional[str] = None, profile: Optional[str] = None, public_url: Optional[str] = None) -> None:
        self.bucket = bucket
        self.path_template = path_template
        self.region = region
        self.profile = profile
        self.public_url_template = public_url

    def publish(self, context: PublishContext) -> UploadResult:
        key = self.path_template.format(
            channel=context.manifest.channel,
            version=context.manifest.version,
            filename=context.archive_path.name,
        )
        url = self._build_public_url(context, key)

        cmd = ["aws", "s3", "cp", str(context.archive_path), f"s3://{self.bucket}/{key}"]
        if self.region:
            cmd.extend(["--region", self.region])
        if self.profile:
            cmd.extend(["--profile", self.profile])

        logs = ["Executing S3 upload", " ".join(cmd)]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.stdout:
            logs.append(proc.stdout.strip())
        if proc.stderr:
            logs.append(proc.stderr.strip())
        status = "succeeded" if proc.returncode == 0 else "failed"
        return UploadResult(
            adapter=self.name,
            status=status,
            url=url,
            logs=logs,
            details={"returncode": proc.returncode, "key": key},
        )

    def _build_public_url(self, context: PublishContext, key: str) -> str:
        if self.public_url_template:
            return self.public_url_template.format(
                channel=context.manifest.channel,
                version=context.manifest.version,
                filename=Path(key).name,
                key=key,
            )
        region = self.region or "us-east-1"
        return f"https://{self.bucket}.s3.{region}.amazonaws.com/{key}"
