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
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml


COMPLETABLE_PHASES = {"dev", "dev-complete", "complete"}
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


def run_git(repo_path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command in the given repository."""
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def branch_exists(repo_path: Path, branch: str, remote: bool = False) -> bool:
    """Check whether a local or remote branch exists."""
    ref = f"refs/remotes/origin/{branch}" if remote else f"refs/heads/{branch}"
    result = run_git(repo_path, ["show-ref", "--verify", "--quiet", ref])
    return result.returncode == 0


def is_ancestor(repo_path: Path, older_ref: str, newer_ref: str) -> bool:
    """True when older_ref is reachable from newer_ref."""
    result = run_git(repo_path, ["merge-base", "--is-ancestor", older_ref, newer_ref])
    return result.returncode == 0


def discover_control_root(governance_repo: Path, control_repo_arg: str) -> Path:
    """Resolve control repo root for target_repos local paths."""
    if control_repo_arg:
        return Path(control_repo_arg).resolve()

    # Best-effort auto-detection from governance repo parents.
    for parent in [governance_repo, *governance_repo.parents]:
        if (parent / ".git").exists() and (parent / "TargetProjects").exists():
            return parent

    return Path.cwd().resolve()


def resolve_repo_path(control_root: Path, local_path: str) -> Path:
    """Resolve a target repo path, allowing absolute or control-root-relative values."""
    candidate = Path(local_path)
    if candidate.is_absolute():
        return candidate
    return (control_root / candidate).resolve()


def feature_branch_candidates(feature_data: dict) -> list[str]:
    """Return likely feature branch names used for implementation branches."""
    candidates: list[str] = []
    feature_id = str(feature_data.get("featureId") or "").strip()
    feature_slug = str(feature_data.get("featureSlug") or "").strip()
    domain = str(feature_data.get("domain") or "").strip()
    service = str(feature_data.get("service") or "").strip()

    for item in [feature_id, feature_slug]:
        if item and item not in candidates:
            candidates.append(item)

    if feature_id and domain and service:
        legacy = f"{domain}-{service}-{feature_id}"
        if legacy not in candidates:
            candidates.append(legacy)

    return candidates


def evaluate_target_repo_branches(
    feature_data: dict,
    governance_repo: Path,
    control_root: Path,
    apply_cleanup: bool,
) -> dict:
    """Validate target repo feature branches are merged; optionally delete merged branches."""
    target_repos = feature_data.get("target_repos") or []
    candidates = feature_branch_candidates(feature_data)

    repo_results: list[dict] = []
    blockers: list[str] = []
    issues: list[str] = []

    for target in target_repos:
        repo_name = str(target.get("name") or "unknown")
        local_path = str(target.get("local_path") or "").strip()
        default_branch = str(target.get("default_branch") or target.get("branch") or "main").strip()

        if not local_path:
            issues.append(f"Target repo '{repo_name}' has no local_path; skipped branch validation")
            repo_results.append({
                "repo": repo_name,
                "status": "skipped",
                "reason": "missing_local_path",
            })
            continue

        repo_path = resolve_repo_path(control_root, local_path)
        if not (repo_path / ".git").exists():
            issues.append(f"Target repo '{repo_name}' not found at '{repo_path}'; skipped branch validation")
            repo_results.append({
                "repo": repo_name,
                "status": "skipped",
                "reason": "repo_not_found",
                "path": str(repo_path),
            })
            continue

        fetch_result = run_git(repo_path, ["fetch", "--prune", "origin"])
        if fetch_result.returncode != 0:
            issues.append(f"Target repo '{repo_name}': failed to fetch origin ({fetch_result.stderr.strip()})")

        base_ref = f"origin/{default_branch}"
        base_exists = branch_exists(repo_path, default_branch, remote=True)
        if not base_exists:
            blockers.append(
                f"Target repo '{repo_name}': base branch '{default_branch}' not found on origin"
            )
            repo_results.append({
                "repo": repo_name,
                "status": "blocked",
                "reason": "base_branch_missing",
                "base_branch": default_branch,
                "path": str(repo_path),
            })
            continue

        checked_branches: list[dict] = []
        repo_blocked = False
        for branch in candidates:
            local_exists = branch_exists(repo_path, branch, remote=False)
            remote_exists = branch_exists(repo_path, branch, remote=True)
            if not local_exists and not remote_exists:
                continue

            branch_info: dict = {
                "branch": branch,
                "local_exists": local_exists,
                "remote_exists": remote_exists,
                "merged_to_base": True,
                "deleted_local": False,
                "deleted_remote": False,
            }

            local_merged = True
            remote_merged = True
            if local_exists:
                local_merged = is_ancestor(repo_path, branch, base_ref)
            if remote_exists:
                remote_merged = is_ancestor(repo_path, f"origin/{branch}", base_ref)

            merged = local_merged and remote_merged
            branch_info["merged_to_base"] = merged

            if not merged:
                repo_blocked = True
                blockers.append(
                    f"Target repo '{repo_name}': branch '{branch}' is not fully merged into '{default_branch}'"
                )
                checked_branches.append(branch_info)
                continue

            if apply_cleanup:
                if local_exists:
                    current_branch = run_git(repo_path, ["branch", "--show-current"]).stdout.strip()
                    if current_branch == branch:
                        checkout_base = run_git(repo_path, ["checkout", default_branch])
                        if checkout_base.returncode != 0:
                            issues.append(
                                f"Target repo '{repo_name}': failed to checkout '{default_branch}' before deleting '{branch}'"
                            )
                        else:
                            current_branch = default_branch
                    if current_branch != branch:
                        delete_local = run_git(repo_path, ["branch", "-D", branch])
                        if delete_local.returncode == 0:
                            branch_info["deleted_local"] = True
                        else:
                            issues.append(
                                f"Target repo '{repo_name}': failed to delete local branch '{branch}'"
                            )

                if remote_exists:
                    delete_remote = run_git(repo_path, ["push", "origin", "--delete", branch])
                    if delete_remote.returncode == 0:
                        branch_info["deleted_remote"] = True
                    else:
                        issues.append(
                            f"Target repo '{repo_name}': failed to delete remote branch '{branch}'"
                        )

            checked_branches.append(branch_info)

        status = "blocked" if repo_blocked else "ok"
        repo_results.append({
            "repo": repo_name,
            "status": status,
            "base_branch": default_branch,
            "path": str(repo_path),
            "branches": checked_branches,
        })

    return {
        "repositories": repo_results,
        "blockers": blockers,
        "issues": issues,
    }


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
            f"Feature phase is '{phase}' — must be 'dev', 'dev-complete', or 'complete' to finalize "
            f"(current phase does not permit archiving)"
        )

    # Retrospective check
    if not retrospective_exists:
        issues.append("retrospective.md not found — run retrospective before finalizing or confirm skip")

    # Target repo branch merge / cleanup readiness checks
    governance_root = Path(args.governance_repo).resolve()
    control_root = discover_control_root(governance_root, getattr(args, "control_repo", ""))
    branch_validation = evaluate_target_repo_branches(
        data,
        governance_root,
        control_root,
        apply_cleanup=False,
    )
    blockers.extend(branch_validation["blockers"])
    issues.extend(branch_validation["issues"])

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
        "target_repo_validation": branch_validation,
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

    governance_root = Path(args.governance_repo).resolve()
    control_root = discover_control_root(governance_root, getattr(args, "control_repo", ""))
    branch_validation = evaluate_target_repo_branches(
        feature_data,
        governance_root,
        control_root,
        apply_cleanup=not dry_run,
    )
    if branch_validation["blockers"]:
        return {
            "status": "fail",
            "feature_id": feature_id,
            "error": "target_repo_branches_not_merged",
            "blockers": branch_validation["blockers"],
            "target_repo_validation": branch_validation,
        }

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
            "target_repo_validation": branch_validation,
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
        "target_repo_validation": branch_validation,
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
    pre_p.add_argument("--control-repo", default="", help="Optional control repo root for resolving target_repos local paths")

    # finalize
    fin_p = subparsers.add_parser("finalize", help="Archive the feature")
    fin_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    fin_p.add_argument("--feature-id", required=True, help="Feature identifier")
    fin_p.add_argument("--domain", default="", help="Domain name (used to locate feature)")
    fin_p.add_argument("--service", default="", help="Service name (used to locate feature)")
    fin_p.add_argument("--control-repo", default="", help="Optional control repo root for resolving target_repos local paths")
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
