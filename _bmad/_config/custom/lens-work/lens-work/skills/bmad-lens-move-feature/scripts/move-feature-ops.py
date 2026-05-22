#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Move feature operations — validate, execute, and patch references for feature relocations.

Subcommands:
  validate         — Check preconditions before moving a feature
  move             — Execute the directory move and update feature.yaml + feature-index.yaml
  patch-references — Replace old path strings in all dependent feature files
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

# Per spec: ^[a-z0-9][a-z0-9-]{0,63}$
VALID_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# Story statuses that block a feature move
BLOCKING_STORY_STATUSES = {"in-progress", "done"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def validate_slug(value: str, field: str) -> str | None:
    """Return an error message if *value* is not a valid slug, else None."""
    if not VALID_SLUG_PATTERN.match(value):
        return (
            f"Invalid {field}: '{value}'. "
            f"Must match ^[a-z0-9][a-z0-9-]{{0,63}}$ "
            f"(lowercase alphanumeric and hyphens only)."
        )
    return None


def get_feature_dir(governance_repo: str, domain: str, service: str, feature_id: str) -> Path:
    """Compute the canonical feature directory path."""
    return Path(governance_repo) / "features" / domain / service / feature_id


def find_feature(governance_repo: str, feature_id: str) -> Path | None:
    """Find a feature.yaml by featureId, scanning all domain/service directories."""
    features_dir = Path(governance_repo) / "features"
    if not features_dir.exists():
        return None
    for yaml_file in features_dir.rglob("feature.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data and data.get("featureId") == feature_id:
                return yaml_file
        except (yaml.YAMLError, OSError):
            continue
    return None


def get_blocking_stories(feature_dir: Path) -> list[dict]:
    """Return stories with blocking status (in-progress or done) inside *feature_dir*."""
    blockers: list[dict] = []

    for plan_file in feature_dir.rglob("sprint-plan.yaml"):
        try:
            with open(plan_file) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            for story in data.get("stories") or []:
                if story.get("status") in BLOCKING_STORY_STATUSES:
                    blockers.append(
                        {
                            "file": str(plan_file.relative_to(feature_dir)),
                            "story": story.get("id", "unknown"),
                            "status": story.get("status"),
                        }
                    )
        except (yaml.YAMLError, OSError):
            continue

    for story_file in feature_dir.rglob("story-*.yaml"):
        try:
            with open(story_file) as f:
                data = yaml.safe_load(f)
            if data and data.get("status") in BLOCKING_STORY_STATUSES:
                blockers.append(
                    {
                        "file": str(story_file.relative_to(feature_dir)),
                        "story": data.get("id", story_file.stem),
                        "status": data.get("status"),
                    }
                )
        except (yaml.YAMLError, OSError):
            continue

    return blockers


def find_dependent_features(governance_repo: str, feature_id: str) -> list[str]:
    """Return feature IDs that reference *feature_id* in depends_on, blocks, or related."""
    features_dir = Path(governance_repo) / "features"
    if not features_dir.exists():
        return []

    dependents: list[str] = []
    for yaml_file in features_dir.rglob("feature.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if not data or data.get("featureId") == feature_id:
                continue
            deps = data.get("dependencies") or {}
            depends_on = list(deps.get("depends_on") or [])
            blocks_list = list(deps.get("blocks") or [])
            related = list(deps.get("related") or [])
            if feature_id in depends_on + blocks_list + related:
                dependents.append(data["featureId"])
        except (yaml.YAMLError, OSError):
            continue

    return dependents


def load_feature_index(governance_repo: str) -> tuple[Path, dict]:
    """Load feature-index.yaml. Returns (path, data) — data has empty features list if missing."""
    index_path = Path(governance_repo) / "feature-index.yaml"
    if index_path.exists():
        try:
            with open(index_path) as f:
                data = yaml.safe_load(f)
            return index_path, data or {"features": []}
        except (yaml.YAMLError, OSError):
            pass
    return index_path, {"features": []}


def atomic_write_yaml(path: Path, data: dict) -> None:
    """Write YAML atomically via temp file + rename to prevent corruption."""
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> dict:
    """Check if a feature can be moved — validates preconditions without touching anything."""
    for field, value in [
        ("feature-id", args.feature_id),
        ("target-domain", args.target_domain),
        ("target-service", args.target_service),
    ]:
        err = validate_slug(value, field)
        if err:
            return {"status": "fail", "error": err}

    feature_yaml = find_feature(args.governance_repo, args.feature_id)
    if not feature_yaml:
        return {"status": "fail", "error": f"Feature not found: {args.feature_id}"}

    try:
        with open(feature_yaml) as f:
            feature_data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "error": f"Failed to read feature.yaml: {e}"}

    current_domain = feature_data.get("domain", "")
    current_service = feature_data.get("service", "")
    current_dir = feature_yaml.parent

    blockers: list[str] = []

    target_dir = get_feature_dir(
        args.governance_repo, args.target_domain, args.target_service, args.feature_id
    )
    if target_dir.exists():
        blockers.append(
            f"Target path already exists: "
            f"features/{args.target_domain}/{args.target_service}/{args.feature_id}"
        )

    if str(current_dir) == str(target_dir):
        blockers.append("Target is the same as the current location")

    blocking_stories = get_blocking_stories(current_dir)
    if blocking_stories:
        ids = ", ".join(s["story"] for s in blocking_stories)
        blockers.append(
            f"Feature has {len(blocking_stories)} in-progress or done "
            f"story/stories that block a move: {ids}"
        )

    dependent_features = find_dependent_features(args.governance_repo, args.feature_id)

    return {
        "status": "fail" if blockers else "pass",
        "feature_id": args.feature_id,
        "from": {"domain": current_domain, "service": current_service},
        "to": {"domain": args.target_domain, "service": args.target_service},
        "blockers": blockers,
        "dependent_features": dependent_features,
    }


def cmd_move(args: argparse.Namespace) -> dict:
    """Execute the feature move: directory rename + YAML update + index update."""
    for field, value in [
        ("feature-id", args.feature_id),
        ("target-domain", args.target_domain),
        ("target-service", args.target_service),
    ]:
        err = validate_slug(value, field)
        if err:
            return {"status": "fail", "error": err}

    feature_yaml = find_feature(args.governance_repo, args.feature_id)
    if not feature_yaml:
        return {"status": "fail", "error": f"Feature not found: {args.feature_id}"}

    try:
        with open(feature_yaml) as f:
            feature_data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "error": f"Failed to read feature.yaml: {e}"}

    current_dir = feature_yaml.parent
    governance_root = Path(args.governance_repo)
    target_dir = get_feature_dir(
        args.governance_repo, args.target_domain, args.target_service, args.feature_id
    )

    if target_dir.exists():
        rel = target_dir.relative_to(governance_root)
        return {"status": "fail", "error": f"Target path already exists: {rel}"}

    if str(current_dir) == str(target_dir):
        return {"status": "fail", "error": "Target is the same as the current location"}

    blocking_stories = get_blocking_stories(current_dir)
    if blocking_stories:
        ids = ", ".join(s["story"] for s in blocking_stories)
        return {
            "status": "fail",
            "error": f"Cannot move: feature has in-progress or done stories: {ids}",
        }

    old_path = str(current_dir.relative_to(governance_root))
    new_path = str(target_dir.relative_to(governance_root))
    files_moved = sum(1 for p in current_dir.rglob("*") if p.is_file())

    if args.dry_run:
        return {
            "status": "pass",
            "dry_run": True,
            "old_path": old_path,
            "new_path": new_path,
            "index_updated": True,
            "files_moved": files_moved,
        }

    # Step 1: move directory
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(current_dir), str(target_dir))
    except OSError as e:
        return {"status": "fail", "error": f"Failed to move directory: {e}"}

    # Step 2: update feature.yaml domain/service
    feature_data["domain"] = args.target_domain
    feature_data["service"] = args.target_service
    try:
        atomic_write_yaml(target_dir / "feature.yaml", feature_data)
    except Exception as e:
        return {"status": "fail", "error": f"Failed to update feature.yaml after move: {e}"}

    # Step 3: update feature-index.yaml
    index_path, index_data = load_feature_index(args.governance_repo)
    index_updated = False
    for entry in index_data.get("features") or []:
        if entry.get("id") == args.feature_id:
            entry["domain"] = args.target_domain
            entry["service"] = args.target_service
            index_updated = True
            break
    if index_updated:
        try:
            atomic_write_yaml(index_path, index_data)
        except Exception as e:
            return {"status": "fail", "error": f"Failed to update feature-index.yaml: {e}"}

    return {
        "status": "pass",
        "old_path": old_path,
        "new_path": new_path,
        "index_updated": index_updated,
        "files_moved": files_moved,
    }


def cmd_patch_references(args: argparse.Namespace) -> dict:
    """Replace old path strings with new path in all text files under features/."""
    old_path_str = args.old_path
    new_path_str = args.new_path

    if ".." in old_path_str or ".." in new_path_str:
        return {"status": "fail", "error": "Path traversal sequences ('..') are not allowed"}

    features_dir = Path(args.governance_repo) / "features"
    if not features_dir.exists():
        return {"status": "pass", "files_patched": 0, "changes": []}

    governance_root = Path(args.governance_repo)
    text_extensions = {".md", ".yaml", ".yml", ".txt", ".json"}
    changes: list[dict] = []

    for file_path in features_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix not in text_extensions:
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        if old_path_str not in content:
            continue

        new_content = content.replace(old_path_str, new_path_str)
        changes.append(
            {
                "file": str(file_path.relative_to(governance_root)),
                "old": old_path_str,
                "new": new_path_str,
            }
        )
        if not args.dry_run:
            try:
                file_path.write_text(new_content, encoding="utf-8")
            except OSError as e:
                rel = file_path.relative_to(governance_root)
                return {"status": "fail", "error": f"Failed to patch {rel}: {e}"}

    result: dict = {
        "status": "pass",
        "files_patched": len(changes),
        "changes": changes,
    }
    if args.dry_run:
        result["dry_run"] = True
    return result


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Move feature operations — validate, execute, and patch references."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = sub.add_parser("validate", help="Check if a feature can be moved")
    p_val.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    p_val.add_argument("--feature-id", required=True, help="Feature ID to move")
    p_val.add_argument("--domain", default="", help="Current domain (optional verification)")
    p_val.add_argument("--service", default="", help="Current service (optional verification)")
    p_val.add_argument("--target-domain", required=True, help="Target domain slug")
    p_val.add_argument("--target-service", required=True, help="Target service slug")

    # move
    p_move = sub.add_parser("move", help="Execute the feature move")
    p_move.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    p_move.add_argument("--feature-id", required=True, help="Feature ID to move")
    p_move.add_argument("--domain", default="", help="Current domain (optional verification)")
    p_move.add_argument("--service", default="", help="Current service (optional verification)")
    p_move.add_argument("--target-domain", required=True, help="Target domain slug")
    p_move.add_argument("--target-service", required=True, help="Target service slug")
    p_move.add_argument("--dry-run", action="store_true", help="Preview without executing")

    # patch-references
    p_patch = sub.add_parser(
        "patch-references", help="Patch old path strings in dependent features"
    )
    p_patch.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    p_patch.add_argument("--feature-id", required=True, help="Feature ID (for context)")
    p_patch.add_argument("--old-path", required=True, help="Old domain/service path to replace")
    p_patch.add_argument("--new-path", required=True, help="New domain/service path")
    p_patch.add_argument("--dry-run", action="store_true", help="Preview without patching")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "validate": cmd_validate,
        "move": cmd_move,
        "patch-references": cmd_patch_references,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()
    sys.exit(0 if result.get("status") == "pass" else 1)


if __name__ == "__main__":
    main()
