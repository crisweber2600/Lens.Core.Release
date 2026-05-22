#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Feature split operations — validate, create, and move stories between features.

The split-feature skill divides a feature's scope or stories into two features.
The critical constraint: stories with in-progress dev work CANNOT be split.
"""

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
IN_PROGRESS_STATUS = "in-progress"
ELIGIBLE_STATUSES = {"pending", "done", "blocked", "backlog", "ready-for-dev", "review"}


def validate_identifier(value: str, field_name: str) -> str | None:
    """Validate that a path-constructing identifier is safe. Returns error message or None."""
    if not SAFE_ID_PATTERN.match(value):
        return (
            f"Invalid {field_name}: '{value}'. "
            f"Must match [a-z0-9][a-z0-9._-]{{0,63}} (lowercase alphanumeric, dots, hyphens, underscores)."
        )
    return None


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def atomic_write_yaml(path: Path, data: dict) -> None:
    """Write YAML atomically via temp file + rename to prevent corruption."""
    dir_path = path.parent
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        os.replace(tmp_path, str(path))
    except Exception:
        os.unlink(tmp_path)
        raise


def get_feature_dir(governance_repo: str, domain: str, service: str, feature_id: str) -> Path:
    """Compute the feature directory path."""
    return Path(governance_repo) / "features" / domain / service / feature_id


def get_feature_index_path(governance_repo: str) -> Path:
    """Return path to the feature-index.yaml."""
    return Path(governance_repo) / "feature-index.yaml"


def parse_sprint_plan(sprint_plan_path: str) -> dict[str, str]:
    """Parse a sprint-plan file and return a dict mapping story IDs to statuses.

    Handles multiple formats:
    1. Pure YAML with development_status: section
    2. Pure YAML with stories: {id: {status: ...}} section
    3. Markdown with embedded YAML code blocks
    4. Simple key: value line pairs
    """
    path = Path(sprint_plan_path)
    if not path.exists():
        return {}

    content = path.read_text(encoding="utf-8")

    # Try parsing the whole file as YAML first
    statuses = _extract_statuses_from_yaml_str(content)
    if statuses:
        return statuses

    # Try extracting YAML blocks from markdown code fences
    yaml_blocks = re.findall(r"```(?:yaml|yml)?\s*\n(.*?)```", content, re.DOTALL)
    for block in yaml_blocks:
        statuses = _extract_statuses_from_yaml_str(block)
        if statuses:
            return statuses

    # Fall back to line-by-line: "story-id: status" patterns
    statuses = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([a-z0-9][a-z0-9._-]{0,63})\s*:\s*([a-z-]+)\s*$", line)
        if match:
            story_id, status = match.group(1), match.group(2)
            statuses[story_id] = status

    return statuses


def _extract_statuses_from_yaml_str(content: str) -> dict[str, str]:
    """Try to extract story_id -> status mappings from a YAML string."""
    try:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return {}

        # Format: development_status: {story-id: status}
        dev_status = data.get("development_status")
        if isinstance(dev_status, dict):
            return {k: str(v) for k, v in dev_status.items() if isinstance(v, str)}

        # Format: stories: {story-id: {status: ...}}
        stories = data.get("stories")
        if isinstance(stories, dict):
            result = {}
            for story_id, story_data in stories.items():
                if isinstance(story_data, dict) and "status" in story_data:
                    result[story_id] = str(story_data["status"])
                elif isinstance(story_data, str):
                    result[story_id] = story_data
            if result:
                return result

    except yaml.YAMLError:
        pass

    return {}


def get_story_status_from_file(story_path: Path) -> str | None:
    """Read a story file and return its status if found, else None."""
    try:
        content = story_path.read_text(encoding="utf-8")
    except OSError:
        return None

    # Try YAML front matter (--- ... ---)
    front_matter_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if front_matter_match:
        try:
            data = yaml.safe_load(front_matter_match.group(1))
            if isinstance(data, dict) and "status" in data:
                return str(data["status"])
        except yaml.YAMLError:
            pass

    # Try parsing whole file as YAML
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and "status" in data:
            return str(data["status"])
    except yaml.YAMLError:
        pass

    # Try inline pattern: "status: in-progress"
    match = re.search(r"^\s*status\s*:\s*([a-z-]+)\s*$", content, re.MULTILINE)
    if match:
        return match.group(1)

    return None


def parse_story_ids(raw: str) -> list[str]:
    """Parse story IDs from comma-separated string or JSON array."""
    raw = raw.strip()
    if raw.startswith("["):
        try:
            ids = json.loads(raw)
            return [str(i).strip() for i in ids if str(i).strip()]
        except json.JSONDecodeError:
            pass
    return [s.strip() for s in raw.split(",") if s.strip()]


# ---------------------------------------------------------------------------
# Subcommand: validate-split
# ---------------------------------------------------------------------------


def cmd_validate_split(args: argparse.Namespace) -> dict:
    """Check if a set of stories can be split (none may be in-progress)."""
    story_ids = parse_story_ids(args.story_ids)
    if not story_ids:
        return {"status": "fail", "error": "No story IDs provided.", "eligible": [], "blocked": [], "blockers": []}

    sprint_statuses = parse_sprint_plan(args.sprint_plan_file)

    eligible = []
    blocked = []

    for story_id in story_ids:
        status = sprint_statuses.get(story_id)
        if status == IN_PROGRESS_STATUS:
            blocked.append({"id": story_id, "reason": IN_PROGRESS_STATUS})
        else:
            eligible.append(story_id)

    overall = "fail" if blocked else "pass"
    return {
        "status": overall,
        "eligible": eligible,
        "blocked": blocked,
        "blockers": [b["id"] for b in blocked],
    }


# ---------------------------------------------------------------------------
# Subcommand: create-split-feature
# ---------------------------------------------------------------------------


def cmd_create_split_feature(args: argparse.Namespace) -> dict:
    """Create a new feature from a split — feature.yaml, index entry, summary stub."""
    # Validate all identifiers
    for field_name, value in [
        ("source-feature-id", args.source_feature_id),
        ("source-domain", args.source_domain),
        ("source-service", args.source_service),
        ("new-feature-id", args.new_feature_id),
    ]:
        err = validate_identifier(value, field_name)
        if err:
            return {"status": "fail", "error": err}

    governance_repo = args.governance_repo
    new_feature_dir = get_feature_dir(governance_repo, args.source_domain, args.source_service, args.new_feature_id)
    new_feature_yaml_path = new_feature_dir / "feature.yaml"
    new_summary_path = new_feature_dir / "summary.md"
    index_path = get_feature_index_path(governance_repo)

    if new_feature_yaml_path.exists():
        return {"status": "fail", "error": f"Feature already exists: {new_feature_yaml_path}"}

    timestamp = now_iso()

    # Build new feature.yaml based on source metadata
    new_feature_data = _build_new_feature_yaml(args, timestamp)

    # Build index entry
    index_entry = {
        "featureId": args.new_feature_id,
        "name": args.new_name,
        "domain": args.source_domain,
        "service": args.source_service,
        "status": "preplan",
        "track": args.track,
        "split_from": args.source_feature_id,
        "created": timestamp,
    }

    if args.dry_run:
        return {
            "status": "pass",
            "dry_run": True,
            "new_feature_id": args.new_feature_id,
            "new_feature_path": str(new_feature_dir),
            "new_feature_yaml": new_feature_data,
            "index_entry": index_entry,
            "index_updated": True,
            "summary_written": True,
        }

    # Execute: create feature directory
    new_feature_dir.mkdir(parents=True, exist_ok=False)
    stories_dir = new_feature_dir / "stories"
    stories_dir.mkdir(exist_ok=True)

    # Write feature.yaml
    atomic_write_yaml(new_feature_yaml_path, new_feature_data)

    # Write summary stub
    summary_content = _build_summary_stub(args, timestamp)
    new_summary_path.write_text(summary_content, encoding="utf-8")

    # Update feature-index.yaml
    index_updated = _update_feature_index(index_path, index_entry)

    return {
        "status": "pass",
        "new_feature_id": args.new_feature_id,
        "new_feature_path": str(new_feature_dir),
        "new_feature_yaml": str(new_feature_yaml_path),
        "summary_path": str(new_summary_path),
        "index_updated": index_updated,
    }


def _build_new_feature_yaml(args: argparse.Namespace, timestamp: str) -> dict:
    """Build the feature.yaml content for the new split feature."""
    team = []
    if args.username:
        team = [{"username": args.username, "role": "lead"}]

    return {
        "name": args.new_name,
        "description": f"Split from feature '{args.source_feature_id}'.",
        "featureId": args.new_feature_id,
        "domain": args.source_domain,
        "service": args.source_service,
        "phase": "preplan",
        "track": args.track,
        "milestones": {
            "businessplan": None,
            "techplan": None,
            "finalizeplan": None,
            "dev-ready": None,
            "dev-complete": None,
        },
        "team": team,
        "dependencies": {
            "depends_on": [],
            "depended_by": [],
        },
        "target_repos": [],
        "links": {
            "retrospective": None,
            "issues": [],
            "pull_request": None,
        },
        "priority": "medium",
        "created": timestamp,
        "updated": timestamp,
        "phase_transitions": [
            {"phase": "preplan", "timestamp": timestamp, "user": args.username or ""},
        ],
        "split_from": args.source_feature_id,
    }


def _build_summary_stub(args: argparse.Namespace, timestamp: str) -> str:
    """Build the summary.md stub content."""
    return (
        f"# {args.new_name}\n\n"
        f"**Feature ID:** {args.new_feature_id}  \n"
        f"**Domain:** {args.source_domain} / {args.source_service}  \n"
        f"**Phase:** preplan  \n"
        f"**Track:** {args.track}  \n"
        f"**Split from:** {args.source_feature_id}  \n"
        f"**Created:** {timestamp}  \n\n"
        f"<!-- summary stub — populated when planning artifacts are committed -->\n"
    )


def _update_feature_index(index_path: Path, entry: dict) -> bool:
    """Add or update an entry in feature-index.yaml. Returns True on success."""
    if index_path.exists():
        try:
            with open(index_path) as f:
                index_data = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            index_data = {}
    else:
        index_data = {}

    if not isinstance(index_data, dict):
        index_data = {}

    features = index_data.get("features", [])
    if not isinstance(features, list):
        features = []

    # Remove existing entry for this featureId if present
    features = [f for f in features if not (isinstance(f, dict) and f.get("featureId") == entry["featureId"])]
    features.append(entry)
    index_data["features"] = features

    index_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_yaml(index_path, index_data)
    return True


# ---------------------------------------------------------------------------
# Subcommand: move-stories
# ---------------------------------------------------------------------------


def cmd_move_stories(args: argparse.Namespace) -> dict:
    """Move story files from one feature to another."""
    for field_name, value in [
        ("source-feature-id", args.source_feature_id),
        ("source-domain", args.source_domain),
        ("source-service", args.source_service),
        ("target-feature-id", args.target_feature_id),
        ("target-domain", args.target_domain),
        ("target-service", args.target_service),
    ]:
        err = validate_identifier(value, field_name)
        if err:
            return {"status": "fail", "error": err}

    story_ids = parse_story_ids(args.story_ids)
    if not story_ids:
        return {"status": "fail", "error": "No story IDs provided.", "moved": [], "total_moved": 0}

    source_stories_dir = (
        get_feature_dir(args.governance_repo, args.source_domain, args.source_service, args.source_feature_id)
        / "stories"
    )
    target_stories_dir = (
        get_feature_dir(args.governance_repo, args.target_domain, args.target_service, args.target_feature_id)
        / "stories"
    )

    if not source_stories_dir.exists():
        return {"status": "fail", "error": f"Source stories directory not found: {source_stories_dir}"}

    # Resolve story files and check for in-progress stories
    resolved = []
    blocked = []
    not_found = []

    for story_id in story_ids:
        story_file = _find_story_file(source_stories_dir, story_id)
        if story_file is None:
            not_found.append(story_id)
            continue

        status = get_story_status_from_file(story_file)
        if status == IN_PROGRESS_STATUS:
            blocked.append({"id": story_id, "reason": IN_PROGRESS_STATUS, "file": str(story_file)})
        else:
            resolved.append((story_id, story_file))

    if blocked:
        return {
            "status": "fail",
            "error": "Cannot move in-progress stories.",
            "blocked": blocked,
            "not_found": not_found,
            "moved": [],
            "total_moved": 0,
        }

    if not_found:
        return {
            "status": "fail",
            "error": f"Story files not found in source: {not_found}",
            "not_found": not_found,
            "moved": [],
            "total_moved": 0,
        }

    if args.dry_run:
        return {
            "status": "pass",
            "dry_run": True,
            "moved": [
                {"id": sid, "from": str(sf), "to": str(target_stories_dir / sf.name)}
                for sid, sf in resolved
            ],
            "total_moved": len(resolved),
        }

    # Execute moves
    target_stories_dir.mkdir(parents=True, exist_ok=True)
    moved = []
    for story_id, story_file in resolved:
        target_path = target_stories_dir / story_file.name
        shutil.move(str(story_file), str(target_path))
        moved.append({"id": story_id, "from": str(story_file), "to": str(target_path)})

    return {
        "status": "pass",
        "moved": moved,
        "total_moved": len(moved),
    }


def _find_story_file(stories_dir: Path, story_id: str) -> Path | None:
    """Find a story file by story ID (tries .md and .yaml extensions)."""
    for ext in (".md", ".yaml", ".yml"):
        candidate = stories_dir / f"{story_id}{ext}"
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Feature split operations — validate, create, and move stories between features.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s validate-split --sprint-plan-file /path/to/sprint-plan.md \\
    --story-ids "story-1,story-2,story-3"

  %(prog)s create-split-feature --governance-repo /repo \\
    --source-feature-id auth-login --source-domain platform --source-service identity \\
    --new-feature-id auth-mfa --new-name "MFA Authentication" --track quickplan --username cweber

  %(prog)s move-stories --governance-repo /repo \\
    --source-feature-id auth-login --source-domain platform --source-service identity \\
    --target-feature-id auth-mfa --target-domain platform --target-service identity \\
    --story-ids "story-3,story-4"
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate-split
    vs = subparsers.add_parser("validate-split", help="Check if stories can be split (none in-progress)")
    vs.add_argument("--sprint-plan-file", required=True, help="Path to sprint-plan.md")
    vs.add_argument("--story-ids", required=True, help="Comma-separated or JSON array of story IDs")

    # create-split-feature
    csf = subparsers.add_parser("create-split-feature", help="Create a new feature from a split")
    csf.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    csf.add_argument("--source-feature-id", required=True, help="Source feature ID")
    csf.add_argument("--source-domain", required=True, help="Source feature domain")
    csf.add_argument("--source-service", required=True, help="Source feature service")
    csf.add_argument("--new-feature-id", required=True, help="New feature ID")
    csf.add_argument("--new-name", required=True, help="New feature human-readable name")
    csf.add_argument("--track", default="quickplan", help="Lifecycle track for new feature")
    csf.add_argument("--username", default="", help="Username creating the split")
    csf.add_argument("--dry-run", action="store_true", help="Show what would be created without writing")

    # move-stories
    ms = subparsers.add_parser("move-stories", help="Move story files from one feature to another")
    ms.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    ms.add_argument("--source-feature-id", required=True, help="Source feature ID")
    ms.add_argument("--source-domain", required=True, help="Source feature domain")
    ms.add_argument("--source-service", required=True, help="Source feature service")
    ms.add_argument("--target-feature-id", required=True, help="Target feature ID")
    ms.add_argument("--target-domain", required=True, help="Target feature domain")
    ms.add_argument("--target-service", required=True, help="Target feature service")
    ms.add_argument("--story-ids", required=True, help="Comma-separated story IDs to move")
    ms.add_argument("--dry-run", action="store_true", help="Show what would be moved without writing")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "validate-split": cmd_validate_split,
        "create-split-feature": cmd_create_split_feature,
        "move-stories": cmd_move_stories,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()

    status = result.get("status", "fail")
    sys.exit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
