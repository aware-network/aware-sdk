from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

DEFAULT_OUTPUT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PROJECT = "aware-desktop-integration"
DEFAULT_TASK = "terminal-session-management"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate mock Control Center fixtures from current docs.")
    parser.add_argument("--project", default=DEFAULT_PROJECT, help="Project slug to harvest")
    parser.add_argument("--task", default=DEFAULT_TASK, help="Task slug to harvest")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output directory for fixtures")
    parser.add_argument("--thread-id", default="thread-control-center", help="Thread id for generated events")
    parser.add_argument("--process-id", default="proc-terminal-session-management", help="Process id binding")
    parser.add_argument("--environment-id", default="env-aware-dev", help="Environment id binding")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output
    events_dir = output_dir / "events"
    docs_dir = output_dir / "docs"
    events_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    project_path = PROJECT_ROOT / "docs" / "projects" / args.project / "tasks" / args.task
    if not project_path.exists():
        raise SystemExit(f"Expected task path {project_path} not found")

    events = []
    for channel in ("analysis", "design", "implementation"):
        doc_dir = project_path / channel
        if not doc_dir.exists():
            continue
        for file_path in sorted(doc_dir.glob("*.md")):
            fm, body = _split_frontmatter(file_path)
            metadata = fm or {}
            timestamp = _detect_timestamp(metadata, file_path)
            event_id = f"{file_path.stem}"
            events.append(
                {
                    "id": event_id,
                    "thread_id": args.thread_id,
                    "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                    "projection": metadata.get("projection", "ProjectTaskOPG"),
                    "channel": channel,
                    "label": metadata.get("title"),
                    "change_type": "modified",
                    "doc_path": str(file_path.relative_to(PROJECT_ROOT)),
                    "metadata": {
                        "project": args.project,
                        "task": args.task,
                        "title": metadata.get("title"),
                    },
                }
            )
            (docs_dir / f"{event_id}.md").write_text(body, encoding="utf-8")

    events.sort(key=lambda e: e["timestamp"])
    events_file = events_dir / f"{args.thread_id}.json"
    events_file.write_text(json.dumps(events, indent=2), encoding="utf-8")

    # Basic environment/process/thread fixtures
    environments = [
        {
            "id": args.environment_id,
            "name": "Aware Dev",
            "slug": "aware-dev",
            "repo_path": str(PROJECT_ROOT),
        }
    ]
    processes = [
        {
            "id": args.process_id,
            "environment_id": args.environment_id,
            "name": "Terminal Session Management",
            "slug": args.task,
        }
    ]
    threads = [
        {
            "id": args.thread_id,
            "environment_id": args.environment_id,
            "process_id": args.process_id,
            "name": "Control Center",
            "slug": "control-center",
            "main": True,
            "branch_title": None,
        }
    ]

    (output_dir / "environments.json").write_text(json.dumps(environments, indent=2), encoding="utf-8")
    (output_dir / "processes.json").write_text(json.dumps(processes, indent=2), encoding="utf-8")
    (output_dir / "threads.json").write_text(json.dumps(threads, indent=2), encoding="utf-8")


def _split_frontmatter(path: Path) -> tuple[Dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm_text = text[3:end]
            body = text[end + 4 :]
            try:
                return yaml.safe_load(fm_text) or {}, body
            except yaml.YAMLError:
                return {}, text
    return {}, text


def _detect_timestamp(metadata: Dict[str, Any], file_path: Path) -> datetime:
    for key in ("updated", "created"):
        value = metadata.get(key)
        if value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
    # Fallback to filename prefix (ISO-ish)
    try:
        stamp = file_path.stem.split("-", 1)[0]
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except Exception:
        return datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)


if __name__ == "__main__":
    main()
