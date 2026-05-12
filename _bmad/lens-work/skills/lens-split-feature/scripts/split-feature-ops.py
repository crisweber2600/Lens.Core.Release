#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Clean-room split-feature operations for Lens governance artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml


SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
UNSAFE_STORY_ID_RE = re.compile(r'[/\\*?\[\]]|\.\.')
IN_PROGRESS_STATUS = "in-progress"


def fail(error: str, message: str, **extra: object) -> dict:
    payload = {"status": "fail", "error": error, "message": message}
    payload.update(extra)
    return payload


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_status(status: str) -> str:
    text = str(status or "").strip().lower()
    return re.sub(r"[\s_]+", "-", text)


def is_in_progress_status(status: str | None) -> bool:
    return normalize_status(status or "") == IN_PROGRESS_STATUS


def validate_identifier(value: str, field_name: str) -> str | None:
    if SAFE_ID_PATTERN.match(value):
        return None
    return (
        f"Invalid {field_name}: '{value}'. "
        "Must match [a-z0-9][a-z0-9._-]{0,63} (lowercase alphanumeric, dots, hyphens, underscores)."
    )


def validate_story_id(story_id: str) -> str | None:
    """Return an error message if story_id is unsafe for path construction, else None.

    Rejects absolute paths, path-traversal segments (``..``), path separators,
    and glob metacharacters so that story IDs cannot escape intended directories.
    """
    if not story_id:
        return "Story ID cannot be empty."
    if os.path.isabs(story_id):
        return f"Invalid story ID '{story_id}': absolute paths are not allowed."
    if UNSAFE_STORY_ID_RE.search(story_id):
        return (
            f"Invalid story ID '{story_id}': must not contain path separators, "
            "'..' segments, or glob metacharacters."
        )
    return None


def atomic_write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False, allow_unicode=True)
        os.replace(temp_path, str(path))
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def get_feature_dir(governance_repo: str, domain: str, service: str, feature_id: str) -> Path:
    return Path(governance_repo) / "features" / domain / service / feature_id


def get_feature_index_path(governance_repo: str) -> Path:
    return Path(governance_repo) / "feature-index.yaml"


def parse_story_ids(raw_story_ids: str) -> list[str]:
    raw_story_ids = raw_story_ids.strip()
    if not raw_story_ids:
        return []
    if raw_story_ids.startswith("["):
        try:
            values = json.loads(raw_story_ids)
        except json.JSONDecodeError:
            values = None
        if isinstance(values, list):
            return [str(value).strip() for value in values if str(value).strip()]
    return [part.strip() for part in raw_story_ids.split(",") if part.strip()]


def parse_sprint_plan(path_text: str) -> dict[str, str]:
    sprint_plan_path = Path(path_text)
    if not sprint_plan_path.exists():
        return {}

    content = sprint_plan_path.read_text(encoding="utf-8")
    statuses = _extract_statuses_from_yaml_str(content)
    if statuses:
        return statuses

    yaml_blocks = re.findall(r"```(?:yaml|yml)?\s*\n(.*?)```", content, re.DOTALL)
    for block in yaml_blocks:
        statuses = _extract_statuses_from_yaml_str(block)
        if statuses:
            return statuses

    parsed: dict[str, str] = {}
    for line in content.splitlines():
        match = re.match(r"^([a-z0-9][a-z0-9._-]{0,63})\s*:\s*(.+?)\s*$", line.strip())
        if match:
            parsed[match.group(1)] = normalize_status(match.group(2))
    return parsed


def _extract_statuses_from_yaml_str(content: str) -> dict[str, str]:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        return {}

    if not isinstance(data, dict):
        return {}

    development_status = data.get("development_status")
    if isinstance(development_status, dict):
        return {
            str(story_id): normalize_status(status)
            for story_id, status in development_status.items()
            if status is not None
        }

    stories = data.get("stories")
    if isinstance(stories, dict):
        extracted: dict[str, str] = {}
        for story_id, story_data in stories.items():
            if isinstance(story_data, dict) and story_data.get("status") is not None:
                extracted[str(story_id)] = normalize_status(story_data["status"])
            elif story_data is not None and not isinstance(story_data, dict):
                extracted[str(story_id)] = normalize_status(story_data)
        return extracted

    if isinstance(stories, list):
        extracted: dict[str, str] = {}
        for item in stories:
            if isinstance(item, dict):
                item_id = item.get("id") or item.get("story_id") or item.get("storyId")
                item_status = item.get("status")
                if item_id and item_status is not None:
                    extracted[str(item_id)] = normalize_status(item_status)
                    continue
                if len(item) == 1:
                    story_id, story_data = next(iter(item.items()))
                    if isinstance(story_data, dict) and story_data.get("status") is not None:
                        extracted[str(story_id)] = normalize_status(story_data["status"])
                    elif story_data is not None and not isinstance(story_data, dict):
                        extracted[str(story_id)] = normalize_status(story_data)
        return extracted

    return {}


def get_story_status_from_file(story_path: Path) -> str | None:
    try:
        content = story_path.read_text(encoding="utf-8")
    except OSError:
        return None

    front_matter_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if front_matter_match:
        try:
            front_matter = yaml.safe_load(front_matter_match.group(1))
        except yaml.YAMLError:
            front_matter = None
        if isinstance(front_matter, dict) and front_matter.get("status") is not None:
            return normalize_status(front_matter["status"])

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        data = None
    if isinstance(data, dict) and data.get("status") is not None:
        return normalize_status(data["status"])

    inline_match = re.search(r"^\s*status\s*:\s*(.+?)\s*$", content, re.MULTILINE)
    if inline_match:
        return normalize_status(inline_match.group(1))
    return None


def load_feature_index(index_path: Path) -> list[dict]:
    if not index_path.exists():
        return []
    try:
        with index_path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"Failed to read feature-index.yaml: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("feature-index.yaml must contain a YAML mapping")
    features = data.get("features") or []
    if not isinstance(features, list):
        raise RuntimeError("feature-index.yaml must contain a features list")
    return [entry for entry in features if isinstance(entry, dict)]


def feature_exists_in_index(index_path: Path, feature_id: str) -> bool:
    for entry in load_feature_index(index_path):
        existing = str(entry.get("id") or entry.get("featureId") or "").strip()
        if existing == feature_id:
            return True
    return False


def write_feature_index(index_path: Path, new_entry: dict) -> None:
    features = load_feature_index(index_path)
    features.append(new_entry)
    atomic_write_yaml(index_path, {"features": features})


def build_feature_yaml(args: argparse.Namespace, timestamp: str) -> dict:
    return {
        "featureId": args.new_feature_id,
        "name": args.new_name,
        "domain": args.source_domain,
        "service": args.source_service,
        "phase": "preplan",
        "track": args.track,
        "priority": "medium",
        "status": "active",
        "split_from": args.source_feature_id,
        "created": timestamp,
        "updated": timestamp,
        "dependencies": {
            "related": [],
            "depends_on": [],
            "blocks": [],
        },
        "target_repos": [],
        "team": ([{"username": args.username, "role": "lead"}] if args.username else []),
    }


def build_summary_stub(args: argparse.Namespace, timestamp: str) -> str:
    return (
        f"# {args.new_name}\n\n"
        f"Feature ID: {args.new_feature_id}\n\n"
        f"Domain: {args.source_domain}/{args.source_service}\n\n"
        f"Track: {args.track}\n\n"
        f"Split from: {args.source_feature_id}\n\n"
        f"Created: {timestamp}\n"
    )


def find_story_file(stories_dir: Path, story_id: str) -> Path | None:
    for suffix in (".md", ".yaml", ".yml"):
        candidate = stories_dir / f"{story_id}{suffix}"
        if candidate.exists():
            return candidate
    return None


def find_story_file_near_sprint_plan(sprint_plan_path: Path, story_id: str) -> Path | None:
    search_dirs = [sprint_plan_path.parent, sprint_plan_path.parent / "stories"]
    suffixes = (".md", ".yaml", ".yml")

    for directory in search_dirs:
        for suffix in suffixes:
            candidate = directory / f"{story_id}{suffix}"
            if candidate.exists():
                return candidate

        for suffix in suffixes:
            matches = sorted(path for path in directory.glob(f"{story_id}*{suffix}") if path.is_file())
            if matches:
                return matches[0]

    return None


def cmd_validate_split(args: argparse.Namespace) -> dict:
    story_ids = parse_story_ids(args.story_ids)
    if not story_ids:
        return fail("story_ids_missing", "No story IDs provided.", eligible=[], blocked=[], blockers=[])

    for story_id in story_ids:
        err = validate_story_id(story_id)
        if err:
            return fail("invalid_story_id", err, eligible=[], blocked=[], blockers=[])

    sprint_plan_path = Path(args.sprint_plan_file)
    if not sprint_plan_path.exists():
        return fail(
            "sprint_plan_missing",
            f"Sprint plan/status file not found: {sprint_plan_path}",
            eligible=[],
            blocked=[],
            blockers=[],
        )

    try:
        sprint_statuses = parse_sprint_plan(args.sprint_plan_file)
    except OSError as exc:
        return fail(
            "sprint_plan_unreadable",
            f"Cannot read sprint plan/status file: {exc}",
            eligible=[],
            blocked=[],
            blockers=[],
        )

    eligible: list[str] = []
    blocked: list[dict[str, str]] = []
    for story_id in story_ids:
        status = sprint_statuses.get(story_id)
        if status is None:
            story_file = find_story_file_near_sprint_plan(sprint_plan_path, story_id)
            if story_file is not None:
                status = get_story_status_from_file(story_file)
        if is_in_progress_status(status):
            blocked.append({"id": story_id, "reason": IN_PROGRESS_STATUS})
        else:
            eligible.append(story_id)

    if blocked:
        return fail(
            "in_progress_stories",
            "Cannot split stories that are already in progress.",
            eligible=eligible,
            blocked=blocked,
            blockers=[item["id"] for item in blocked],
        )

    return {
        "status": "pass",
        "eligible": eligible,
        "blocked": [],
        "blockers": [],
    }


def cmd_create_split_feature(args: argparse.Namespace) -> dict:
    for field_name, value in (
        ("source-feature-id", args.source_feature_id),
        ("source-domain", args.source_domain),
        ("source-service", args.source_service),
        ("new-feature-id", args.new_feature_id),
    ):
        error = validate_identifier(value, field_name)
        if error:
            return fail("invalid_identifier", error)

    governance_repo = Path(args.governance_repo)
    if not governance_repo.exists():
        return fail(
            "governance_repo_missing",
            f"Governance repo path does not exist: {governance_repo}",
        )
    if not governance_repo.is_dir():
        return fail(
            "governance_repo_not_a_directory",
            f"Governance repo path is not a directory: {governance_repo}",
        )
    index_path = get_feature_index_path(str(governance_repo))
    try:
        duplicate_exists = feature_exists_in_index(index_path, args.new_feature_id)
    except RuntimeError as exc:
        return fail("index_malformed", str(exc))

    if duplicate_exists:
        return fail(
            "duplicate_feature",
            f"Feature '{args.new_feature_id}' is already registered in feature-index.yaml.",
            duplicate_feature_id=args.new_feature_id,
        )

    new_feature_dir = get_feature_dir(str(governance_repo), args.source_domain, args.source_service, args.new_feature_id)
    feature_yaml_path = new_feature_dir / "feature.yaml"
    summary_path = new_feature_dir / "summary.md"
    stories_dir = new_feature_dir / "stories"
    if feature_yaml_path.exists():
        return fail("feature_exists", f"Feature already exists at {feature_yaml_path}")

    timestamp = now_iso()
    feature_yaml = build_feature_yaml(args, timestamp)
    index_entry = {
        "id": args.new_feature_id,
        "domain": args.source_domain,
        "service": args.source_service,
        "status": "preplan",
        "owner": args.username,
        "summary": f"Split from {args.source_feature_id}",
    }

    if args.dry_run:
        return {
            "status": "pass",
            "dry_run": True,
            "new_feature_id": args.new_feature_id,
            "new_feature_path": str(new_feature_dir),
            "feature_yaml": feature_yaml,
            "summary_path": str(summary_path),
            "index_entry": index_entry,
        }

    try:
        stories_dir.mkdir(parents=True, exist_ok=False)
        atomic_write_yaml(feature_yaml_path, feature_yaml)
        summary_path.write_text(build_summary_stub(args, timestamp), encoding="utf-8")
        write_feature_index(index_path, index_entry)
    except FileExistsError:
        return fail("feature_exists", f"Feature already exists at {new_feature_dir}")
    except OSError as exc:
        return fail("write_failed", f"Failed to create split feature artifacts: {exc}")
    except RuntimeError as exc:
        return fail("index_malformed", str(exc))

    return {
        "status": "pass",
        "new_feature_id": args.new_feature_id,
        "new_feature_path": str(new_feature_dir),
        "feature_yaml_path": str(feature_yaml_path),
        "summary_path": str(summary_path),
        "stories_path": str(stories_dir),
    }


def cmd_move_stories(args: argparse.Namespace) -> dict:
    for field_name, value in (
        ("source-feature-id", args.source_feature_id),
        ("source-domain", args.source_domain),
        ("source-service", args.source_service),
        ("target-feature-id", args.target_feature_id),
        ("target-domain", args.target_domain),
        ("target-service", args.target_service),
    ):
        error = validate_identifier(value, field_name)
        if error:
            return fail("invalid_identifier", error, moved=[], total_moved=0)

    story_ids = parse_story_ids(args.story_ids)
    if not story_ids:
        return fail("story_ids_missing", "No story IDs provided.", moved=[], total_moved=0)

    for story_id in story_ids:
        err = validate_story_id(story_id)
        if err:
            return fail("invalid_story_id", err, moved=[], total_moved=0)

    source_stories_dir = get_feature_dir(
        args.governance_repo,
        args.source_domain,
        args.source_service,
        args.source_feature_id,
    ) / "stories"
    target_stories_dir = get_feature_dir(
        args.governance_repo,
        args.target_domain,
        args.target_service,
        args.target_feature_id,
    ) / "stories"

    if not source_stories_dir.exists():
        return fail(
            "source_missing",
            f"Source stories directory not found: {source_stories_dir}",
            moved=[],
            total_moved=0,
        )

    resolved: list[tuple[str, Path]] = []
    blocked: list[dict[str, str]] = []
    not_found: list[str] = []

    for story_id in story_ids:
        story_file = find_story_file(source_stories_dir, story_id)
        if story_file is None:
            not_found.append(story_id)
            continue
        status = get_story_status_from_file(story_file)
        if is_in_progress_status(status):
            blocked.append({"id": story_id, "reason": IN_PROGRESS_STATUS, "file": str(story_file)})
            continue
        resolved.append((story_id, story_file))

    if blocked:
        return fail(
            "in_progress_stories",
            "Cannot move stories that are already in progress.",
            blocked=blocked,
            not_found=not_found,
            moved=[],
            total_moved=0,
        )

    if not_found:
        return fail(
            "stories_not_found",
            f"Story files not found in source: {', '.join(not_found)}",
            not_found=not_found,
            moved=[],
            total_moved=0,
        )

    planned_moves = [
        {"id": story_id, "from": str(story_file), "to": str(target_stories_dir / story_file.name)}
        for story_id, story_file in resolved
    ]

    if args.dry_run:
        return {"status": "pass", "dry_run": True, "moved": planned_moves, "total_moved": len(planned_moves)}

    # Preflight: ensure target directory is accessible and no destination already exists.
    try:
        target_stories_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return fail("write_failed", f"Cannot create target directory: {exc}", moved=[], total_moved=0)

    conflicts = [dest for move in planned_moves if Path(dest := move["to"]).exists()]
    if conflicts:
        return fail(
            "destination_conflict",
            f"Destination files already exist: {', '.join(conflicts)}",
            moved=[],
            total_moved=0,
        )

    # Execute moves with rollback on partial failure.
    completed: list[dict] = []
    try:
        for move in planned_moves:
            shutil.move(move["from"], move["to"])
            completed.append(move)
    except OSError as exc:
        rollback_errors: list[str] = []
        for done in reversed(completed):
            try:
                shutil.move(done["to"], done["from"])
            except OSError as rb_exc:
                rollback_errors.append(str(rb_exc))
        err_msg = f"Failed to move stories: {exc}"
        if rollback_errors:
            err_msg += f" (rollback partially failed: {'; '.join(rollback_errors)})"
        return fail("move_failed", err_msg, moved=[], total_moved=0)

    return {"status": "pass", "moved": planned_moves, "total_moved": len(planned_moves)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Split-feature operations for Lens governance artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_split = subparsers.add_parser("validate-split", help="Validate that selected stories are split-safe")
    validate_split.add_argument("--sprint-plan-file", required=True, help="Path to sprint status or sprint plan file")
    validate_split.add_argument("--story-ids", required=True, help="Comma-separated or JSON array of story IDs")

    create_split = subparsers.add_parser("create-split-feature", help="Create a new feature shell for a split")
    create_split.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    create_split.add_argument("--source-feature-id", required=True, help="Source feature ID")
    create_split.add_argument("--source-domain", required=True, help="Source feature domain")
    create_split.add_argument("--source-service", required=True, help="Source feature service")
    create_split.add_argument("--new-feature-id", required=True, help="New feature ID")
    create_split.add_argument("--new-name", required=True, help="New feature name")
    create_split.add_argument("--track", default="quickplan", help="Lifecycle track for the new feature")
    create_split.add_argument("--username", default="", help="Username creating the split")
    create_split.add_argument("--dry-run", action="store_true", help="Show what would be created without writing")

    move_stories = subparsers.add_parser("move-stories", help="Move story files between split features")
    move_stories.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    move_stories.add_argument("--source-feature-id", required=True, help="Source feature ID")
    move_stories.add_argument("--source-domain", required=True, help="Source feature domain")
    move_stories.add_argument("--source-service", required=True, help="Source feature service")
    move_stories.add_argument("--target-feature-id", required=True, help="Target feature ID")
    move_stories.add_argument("--target-domain", required=True, help="Target feature domain")
    move_stories.add_argument("--target-service", required=True, help="Target feature service")
    move_stories.add_argument("--story-ids", required=True, help="Comma-separated or JSON array of story IDs")
    move_stories.add_argument("--dry-run", action="store_true", help="Show planned moves without writing")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    commands = {
        "validate-split": cmd_validate_split,
        "create-split-feature": cmd_create_split_feature,
        "move-stories": cmd_move_stories,
    }
    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2)
    print()
    raise SystemExit(0 if result.get("status") == "pass" else 1)


if __name__ == "__main__":
    main()