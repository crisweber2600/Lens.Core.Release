#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Complete operations — check preconditions, finalize, and archive Lens features.

The complete skill is the lifecycle endpoint. It validates a feature is ready to
close, archives it atomically (feature.yaml + feature-index.yaml + summary.md),
and provides archive-status queries.
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml


COMPLETABLE_PHASES = {"dev", "complete"}
TERMINAL_PHASE = "complete"
ARCHIVED_STATUS = "archived"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_feature_dir(governance_repo: str, domain: str, service: str, feature_id: str) -> Path:
    """Compute the feature directory path."""
    return Path(governance_repo) / "features" / domain / service / feature_id


def get_feature_path(governance_repo: str, domain: str, service: str, feature_id: str) -> Path:
    """Compute the feature.yaml file path."""
    return get_feature_dir(governance_repo, domain, service, feature_id) / "feature.yaml"


def get_index_path(governance_repo: str) -> Path:
    """Compute the feature-index.yaml path."""
    return Path(governance_repo) / "feature-index.yaml"


def find_feature(governance_repo: str, feature_id: str) -> Path | None:
    """Find a feature.yaml by featureId, searching all domains/services."""
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


def load_yaml(path: Path) -> dict:
    """Load a YAML file. Returns empty dict if missing."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def atomic_write_yaml(path: Path, data: dict) -> None:
    """Write YAML atomically via temp file + rename to prevent corruption."""
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".yaml.tmp")
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


def atomic_write_text(path: Path, content: str) -> None:
    """Write a text file atomically via temp file + rename."""
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def build_summary(feature_data: dict, archived_at: str, retrospective_skipped: bool = False) -> str:
    """Build the final summary.md content for the feature archive."""
    feature_id = feature_data.get("featureId", "unknown")
    name = feature_data.get("name", "Unnamed Feature")
    domain = feature_data.get("domain", "")
    service = feature_data.get("service", "")
    track = feature_data.get("track", "")
    priority = feature_data.get("priority", "")
    created_at = feature_data.get("created_at", "")

    retro_note = ""
    if retrospective_skipped:
        retro_note = "\n> **Note:** Retrospective was skipped at archive time.\n"

    return f"""# Archive Summary: {name}

**Feature ID:** {feature_id}
**Domain:** {domain} / {service}
**Track:** {track}
**Priority:** {priority}
**Created:** {created_at}
**Archived:** {archived_at}
{retro_note}
## Delivered State

This feature has been completed and archived. The feature directory contains
the complete historical record from inception to delivery.

## Archive Contents

- `feature.yaml` — feature identity and lifecycle record (phase: complete)
- `retrospective.md` — retrospective analysis{"" if not retrospective_skipped else " (skipped)"}
- `docs/` — final project documentation
- `summary.md` — this file

## Notes

Review the feature directory for the full planning, implementation, and
retrospective record.
"""


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_check_preconditions(args: argparse.Namespace) -> dict:
    """Validate a feature is ready to be completed."""
    feature_id = args.feature_id

    # Locate feature
    if args.domain and args.service:
        feature_path = get_feature_path(args.governance_repo, args.domain, args.service, feature_id)
        if not feature_path.exists():
            # Fall back to search
            feature_path = find_feature(args.governance_repo, feature_id)
    else:
        feature_path = find_feature(args.governance_repo, feature_id)

    if not feature_path:
        return {
            "status": "fail",
            "feature_id": feature_id,
            "phase": None,
            "retrospective_exists": False,
            "issues": [],
            "blockers": [f"Feature '{feature_id}' not found in governance repo '{args.governance_repo}'"],
        }

    try:
        with open(feature_path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {
            "status": "fail",
            "feature_id": feature_id,
            "phase": None,
            "retrospective_exists": False,
            "issues": [],
            "blockers": [f"Cannot read feature.yaml: {e}"],
        }

    if not data:
        return {
            "status": "fail",
            "feature_id": feature_id,
            "phase": None,
            "retrospective_exists": False,
            "issues": [],
            "blockers": ["feature.yaml is empty or invalid"],
        }

    phase = data.get("phase", "")
    feature_dir = feature_path.parent
    retrospective_path = feature_dir / "retrospective.md"
    retrospective_exists = retrospective_path.exists()

    issues = []
    blockers = []

    # Phase check
    if phase not in COMPLETABLE_PHASES:
        blockers.append(
            f"Feature phase is '{phase}' — must be 'dev' or 'complete' to finalize "
            f"(current phase does not permit archiving)"
        )

    # Retrospective check
    if not retrospective_exists:
        issues.append("retrospective.md not found — run retrospective before finalizing or confirm skip")

    if blockers:
        status = "fail"
    elif issues:
        status = "warn"
    else:
        status = "pass"

    return {
        "status": status,
        "feature_id": feature_id,
        "phase": phase,
        "retrospective_exists": retrospective_exists,
        "issues": issues,
        "blockers": blockers,
    }


def cmd_finalize(args: argparse.Namespace) -> dict:
    """Archive the feature: update feature.yaml, feature-index.yaml, write summary.md."""
    feature_id = args.feature_id
    dry_run = getattr(args, "dry_run", False)

    # Locate feature
    if args.domain and args.service:
        feature_path = get_feature_path(args.governance_repo, args.domain, args.service, feature_id)
        if not feature_path.exists():
            feature_path = find_feature(args.governance_repo, feature_id)
    else:
        feature_path = find_feature(args.governance_repo, feature_id)

    if not feature_path:
        return {
            "status": "fail",
            "feature_id": feature_id,
            "error": f"Feature '{feature_id}' not found in governance repo '{args.governance_repo}'",
        }

    try:
        with open(feature_path) as f:
            feature_data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "feature_id": feature_id, "error": f"Cannot read feature.yaml: {e}"}

    if not feature_data:
        return {"status": "fail", "feature_id": feature_id, "error": "feature.yaml is empty or invalid"}

    archived_at = now_iso()
    feature_dir = feature_path.parent
    retrospective_skipped = not (feature_dir / "retrospective.md").exists()

    # Prepare updated feature data
    updated_feature = dict(feature_data)
    updated_feature["phase"] = TERMINAL_PHASE
    updated_feature["completed_at"] = archived_at

    # Prepare updated feature-index
    index_path = get_index_path(args.governance_repo)
    index_data = load_yaml(index_path)
    index_updated = False

    features_list = index_data.get("features", [])
    for entry in features_list:
        if (entry.get("featureId") or entry.get("id")) == feature_id:
            entry["status"] = ARCHIVED_STATUS
            entry["updated_at"] = archived_at
            index_updated = True
            break

    # Build summary content
    summary_content = build_summary(feature_data, archived_at, retrospective_skipped)
    summary_path = feature_dir / "summary.md"

    if dry_run:
        return {
            "status": "pass",
            "feature_id": feature_id,
            "dry_run": True,
            "archived_at": archived_at,
            "feature_yaml_path": str(feature_path),
            "index_updated": index_updated,
            "changes": {
                "feature_yaml": {"phase": TERMINAL_PHASE, "completed_at": archived_at},
                "feature_index": {"status": ARCHIVED_STATUS} if index_updated else "entry not found — would not update",
                "summary_md": str(summary_path),
            },
        }

    # Atomic writes
    try:
        atomic_write_yaml(feature_path, updated_feature)
    except OSError as e:
        return {"status": "fail", "feature_id": feature_id, "error": f"Failed to write feature.yaml: {e}"}

    if index_updated:
        try:
            atomic_write_yaml(index_path, index_data)
        except OSError as e:
            return {
                "status": "fail",
                "feature_id": feature_id,
                "error": f"feature.yaml updated but failed to write feature-index.yaml: {e}",
                "partial": True,
                "feature_yaml_path": str(feature_path),
            }

    try:
        atomic_write_text(summary_path, summary_content)
    except OSError as e:
        return {
            "status": "fail",
            "feature_id": feature_id,
            "error": f"feature.yaml and index updated but failed to write summary.md: {e}",
            "partial": True,
            "feature_yaml_path": str(feature_path),
            "index_updated": index_updated,
        }

    return {
        "status": "pass",
        "feature_id": feature_id,
        "archived_at": archived_at,
        "feature_yaml_path": str(feature_path),
        "index_updated": index_updated,
    }


def cmd_archive_status(args: argparse.Namespace) -> dict:
    """Check if a feature is archived."""
    feature_id = args.feature_id

    feature_path = find_feature(args.governance_repo, feature_id)
    if not feature_path:
        return {
            "status": "fail",
            "feature_id": feature_id,
            "error": f"Feature '{feature_id}' not found in governance repo '{args.governance_repo}'",
        }

    try:
        with open(feature_path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "feature_id": feature_id, "error": f"Cannot read feature.yaml: {e}"}

    if not data:
        return {"status": "fail", "feature_id": feature_id, "error": "feature.yaml is empty or invalid"}

    phase = data.get("phase", "")
    completed_at = data.get("completed_at", "")
    archived = phase == TERMINAL_PHASE

    return {
        "status": "pass",
        "feature_id": feature_id,
        "archived": archived,
        "phase": phase,
        "completed_at": completed_at,
    }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Complete operations — check preconditions, finalize, and archive Lens features.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s check-preconditions --governance-repo /path/to/repo \\
    --feature-id my-feature --domain platform --service identity

  %(prog)s finalize --governance-repo /path/to/repo \\
    --feature-id my-feature --domain platform --service identity

  %(prog)s finalize --governance-repo /path/to/repo \\
    --feature-id my-feature --domain platform --service identity --dry-run

  %(prog)s archive-status --governance-repo /path/to/repo --feature-id my-feature
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # check-preconditions
    pre_p = subparsers.add_parser("check-preconditions", help="Validate feature is ready to complete")
    pre_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    pre_p.add_argument("--feature-id", required=True, help="Feature identifier")
    pre_p.add_argument("--domain", default="", help="Domain name (used to locate feature)")
    pre_p.add_argument("--service", default="", help="Service name (used to locate feature)")

    # finalize
    fin_p = subparsers.add_parser("finalize", help="Archive the feature")
    fin_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    fin_p.add_argument("--feature-id", required=True, help="Feature identifier")
    fin_p.add_argument("--domain", default="", help="Domain name (used to locate feature)")
    fin_p.add_argument("--service", default="", help="Service name (used to locate feature)")
    fin_p.add_argument("--dry-run", action="store_true", help="Show what would change without writing")

    # archive-status
    arc_p = subparsers.add_parser("archive-status", help="Check if a feature is archived")
    arc_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    arc_p.add_argument("--feature-id", required=True, help="Feature identifier")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "check-preconditions": cmd_check_preconditions,
        "finalize": cmd_finalize,
        "archive-status": cmd_archive_status,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()

    status = result.get("status", "fail")
    exit_code = 0 if status in ("pass", "warn") else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
