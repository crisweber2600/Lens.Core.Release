#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML>=6.0"]
# ///
"""
git-state-ops.py — Read-only git queries for the Lens 2-branch feature model.

Commands:
  feature-state    Derive feature lifecycle state from feature.yaml + branch existence
  branches         Query branches for a specific feature (list|info|exists)
  active-features  Enumerate all features with active branches in the governance repo

Usage:
  git-state-ops.py feature-state --governance-repo REPO --feature-id ID [--include-remote]
  git-state-ops.py branches --governance-repo REPO --feature-id ID --query (list|info|exists) [--branch NAME] [--include-remote]
  git-state-ops.py active-features --governance-repo REPO [--domain D] [--phase P] [--track T] [--status S] [--limit N] [--include-remote]

Exit codes:
  0 — success, no discrepancies
  1 — hard error (repo not found, git failure)
  2 — success, but discrepancies found (feature-state only)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml


GIT_MIN_VERSION = (2, 28)

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git(repo: str, *args) -> tuple[int, str, str]:
    """Run a git command in the given repo. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_git_version() -> str | None:
    """Return error string if git < 2.28, else None."""
    rc, out, _ = git(".", "--version")
    if rc != 0:
        return "git not found on PATH"
    parts = out.split()
    if len(parts) < 3:
        return f"Cannot parse git version: {out}"
    try:
        ver_str = parts[2].split("-")[0]
        segments = ver_str.split(".")
        major, minor = int(segments[0]), int(segments[1])
        if (major, minor) < GIT_MIN_VERSION:
            return f"git {major}.{minor} found; git 2.28+ required"
    except (ValueError, IndexError):
        return f"Cannot parse git version: {out}"
    return None


def get_all_local_branches(repo: str) -> set[str]:
    """Return the set of all local branch names in one git call."""
    rc, out, _ = git(repo, "branch", "--list", "--format=%(refname:short)")
    if rc != 0 or not out:
        return set()
    return {line.strip() for line in out.splitlines() if line.strip()}


def branch_exists(repo: str, branch: str, include_remote: bool = False,
                  local_cache: set[str] | None = None) -> bool:
    """Return True if the branch exists. Uses local_cache when available."""
    if local_cache is not None:
        exists = branch in local_cache
        if exists or not include_remote:
            return exists

    if include_remote:
        # Check local first, then remote tracking ref
        rc, out, _ = git(repo, "branch", "--all", "--list", branch, f"remotes/origin/{branch}")
        return rc == 0 and bool(out.strip())

    rc, out, _ = git(repo, "branch", "--list", branch)
    return rc == 0 and bool(out.strip())


def list_branches_matching(repo: str, pattern: str, include_remote: bool = False) -> list[dict]:
    """Return branches matching a glob pattern with their last-commit info."""
    fmt = "--format=%(refname:short)|%(objectname:short)|%(committerdate:iso-strict)|%(subject)"
    if include_remote:
        rc, out, _ = git(repo, "branch", "--all", "--list", pattern, fmt)
    else:
        rc, out, _ = git(repo, "branch", "--list", pattern, fmt)
    if rc != 0 or not out:
        return []
    results = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            name, sha, date, subject = parts
            results.append({"branch": name, "sha": sha, "date": date, "subject": subject})
    return results


def branch_log(repo: str, branch: str, count: int = 10) -> list[str]:
    """Return the last N commit messages for a branch."""
    rc, out, _ = git(repo, "log", f"-{count}", "--oneline", branch)
    if rc != 0:
        return []
    return out.splitlines()


def ahead_count(repo: str, base: str, head: str) -> int | None:
    """Return number of commits in head not in base, or None if indeterminate."""
    rc, out, _ = git(repo, "rev-list", "--count", f"{base}..{head}")
    if rc != 0:
        return None
    try:
        return int(out.strip())
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Feature YAML resolution
# ---------------------------------------------------------------------------

FEATURE_YAML_SEARCH_ROOTS = ["features"]


def find_feature_yaml(repo: str, feature_id: str) -> Path | None:
    """
    Search for feature.yaml by feature_id under known search roots.
    Tries both flat (features/{featureId}/feature.yaml) and
    domain/service paths (features/{domain}/{service}/{featureId}/feature.yaml).
    """
    repo_path = Path(repo)
    for root in FEATURE_YAML_SEARCH_ROOTS:
        base = repo_path / root
        if not base.exists():
            continue
        candidate = base / feature_id / "feature.yaml"
        if candidate.exists():
            return candidate
        for found in base.rglob(f"{feature_id}/feature.yaml"):
            return found
    return None


def load_feature_yaml(path: Path) -> tuple[dict | None, str | None]:
    """Load a feature.yaml file. Returns (data, error_message)."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None, f"Invalid YAML structure in {path}"
        return data, None
    except yaml.YAMLError as e:
        return None, f"YAML parse error in {path}: {e}"
    except OSError as e:
        return None, f"Cannot read {path}: {e}"


def _feature_summary(fid: str, phase: str | None, plan_exists: bool,
                     dev_branches: list, discrepancies: list, errors: list) -> str:
    """Compute a one-sentence human-readable verdict for feature-state output."""
    if discrepancies:
        return f"WARNING: {len(discrepancies)} discrepancy(ies) — {discrepancies[0]}"
    if errors:
        return f"ERROR: {errors[0]}"
    phase_str = phase or "unknown phase"
    return f"Feature '{fid}' is in {phase_str}, no discrepancies"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_feature_state(args: argparse.Namespace) -> dict:
    repo = args.governance_repo
    fid = args.feature_id
    include_remote = getattr(args, "include_remote", False)

    result: dict = {
        "feature_id": fid,
        "yaml_path": None,
        "phase": None,
        "track": None,
        "status": None,
        "yaml_on_main": False,
        "discrepancies": [],
        "summary": "",
        "errors": [],
    }

    # --- feature.yaml (governance repo keeps everything on main) ---
    yaml_path = find_feature_yaml(repo, fid)
    if yaml_path:
        result["yaml_path"] = str(yaml_path.relative_to(repo))
        result["yaml_on_main"] = True
        data, err = load_feature_yaml(yaml_path)
        if err:
            result["errors"].append(err)
        else:
            result["phase"] = data.get("phase")
            result["track"] = data.get("track")
            result["status"] = data.get("status")
    else:
        result["errors"].append(
            f"feature.yaml not found for '{fid}' — run bmad-lens-feature-yaml to create one"
        )

    # --- discrepancy detection ---
    discrepancies = []

    if result["status"] == "complete" and result["yaml_on_main"]:
        # Complete features should eventually have their feature.yaml removed or archived.
        # This is informational, not necessarily a hard error.
        pass

    result["discrepancies"] = discrepancies
    result["summary"] = _feature_summary(
        fid, result["phase"], False,
        [], discrepancies, result["errors"]
    )
    return result


def cmd_branches(args: argparse.Namespace) -> dict:
    repo = args.governance_repo
    fid = args.feature_id
    query = args.query
    include_remote = getattr(args, "include_remote", False)

    if query == "exists":
        branch = getattr(args, "branch", None) or fid
        return {"branch": branch, "exists": branch_exists(repo, branch, include_remote)}

    if query == "list":
        # Explicit match: base branch + all properly-suffixed variants only (MO-1 fix)
        base_matches = list_branches_matching(repo, fid, include_remote)
        suffixed = list_branches_matching(repo, f"{fid}-*", include_remote)
        branches = base_matches + suffixed
        return {
            "feature_id": fid,
            "branches": branches,
            "count": len(branches),
            "note": "Remote branches not included. Use --include-remote to scan remotes." if not include_remote else None,
        }

    if query == "info":
        branch = getattr(args, "branch", None) or fid
        if not branch_exists(repo, branch, include_remote):
            return {"branch": branch, "exists": False}

        rc, sha, _ = git(repo, "rev-parse", branch)
        _, last_msg, _ = git(repo, "log", "-1", "--format=%s", branch)
        _, author, _ = git(repo, "log", "-1", "--format=%an", branch)
        _, date, _ = git(repo, "log", "-1", "--format=%ci", branch)
        log = branch_log(repo, branch, count=10)
        ahead = ahead_count(repo, fid, branch) if branch != fid else None

        return {
            "branch": branch,
            "exists": True,
            "sha": sha,
            "last_commit_message": last_msg,
            "last_commit_author": author,
            "last_commit_date": date,
            "commits_ahead_of_base": ahead,
            "recent_log": log,
        }

    return {"error": f"Unknown query type: '{query}'. Use list|info|exists"}


def cmd_active_features(args: argparse.Namespace) -> dict:
    """Enumerate features in the governance repo by their feature.yaml metadata.

    The governance repo stays on main — no feature branches exist there.
    This command scans feature.yaml files and reports their lifecycle state.
    """
    repo = args.governance_repo
    domain_filter = getattr(args, "domain", None)
    phase_filter = getattr(args, "phase", None)
    track_filter = getattr(args, "track", None)
    status_filter = getattr(args, "status", None)
    limit = getattr(args, "limit", None)
    include_remote = getattr(args, "include_remote", False)

    repo_path = Path(repo)
    features = []
    ghost_yamls = []

    # Collect all feature.yaml files
    yaml_files = []
    for root in FEATURE_YAML_SEARCH_ROOTS:
        base = repo_path / root
        if not base.exists():
            continue
        yaml_files.extend(base.rglob("feature.yaml"))

    total_scanned = len(yaml_files)
    for i, yaml_file in enumerate(yaml_files):
        if limit and len(features) >= limit:
            break

        if total_scanned > 20:
            print(f"Scanning features: {i + 1}/{total_scanned}", end="\r", file=sys.stderr)

        data, err = load_feature_yaml(yaml_file)
        if err or not data:
            ghost_yamls.append(str(yaml_file.relative_to(repo_path)))
            continue

        fid = data.get("feature_id") or data.get("id")
        if not fid:
            ghost_yamls.append(str(yaml_file.relative_to(repo_path)))
            continue

        # Apply filters
        if domain_filter and data.get("domain") != domain_filter:
            continue
        if phase_filter and data.get("phase") != phase_filter:
            continue
        if track_filter and data.get("track") != track_filter:
            continue
        if status_filter and data.get("status") != status_filter:
            continue

        # Skip completed/cancelled features unless explicitly filtered
        if not status_filter and data.get("status") not in ("active", "paused", None):
            continue

        features.append({
            "feature_id": fid,
            "domain": data.get("domain"),
            "service": data.get("service"),
            "phase": data.get("phase"),
            "track": data.get("track"),
            "status": data.get("status"),
            "yaml_path": str(yaml_file.relative_to(repo_path)),
        })

    if total_scanned > 20:
        print("", file=sys.stderr)  # clear progress line

    return {
        "features": features,
        "ghost_yamls": ghost_yamls,
        "total_active": len(features),
        "scanned": total_scanned,
        "limited": limit is not None and len(features) >= (limit or 0),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only git state queries for the Lens 2-branch feature model.",
        epilog="Exit codes: 0=clean, 1=error, 2=discrepancies found (feature-state only)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # feature-state
    fs = sub.add_parser("feature-state", help="Derive feature state from yaml + branches")
    fs.add_argument("--governance-repo", required=True, help="Path to governance repo")
    fs.add_argument("--feature-id", required=True, help="Feature identifier")
    fs.add_argument("--include-remote", action="store_true", help="Also check remote branches")

    # branches
    br = sub.add_parser("branches", help="Query branches for a feature")
    br.add_argument("--governance-repo", required=True)
    br.add_argument("--feature-id", required=True)
    br.add_argument("--query", required=True, choices=["list", "info", "exists"])
    br.add_argument("--branch", help="Specific branch name (for info/exists queries)")
    br.add_argument("--include-remote", action="store_true")

    # active-features
    af = sub.add_parser("active-features", help="Enumerate features with active branches")
    af.add_argument("--governance-repo", required=True)
    af.add_argument("--domain", help="Filter by domain")
    af.add_argument("--phase", help="Filter by lifecycle phase")
    af.add_argument("--track", help="Filter by execution track")
    af.add_argument("--status", help="Filter by status (active|paused|complete|warning)")
    af.add_argument("--limit", type=int, help="Cap results at N features")
    af.add_argument("--include-remote", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Normalize hyphenated flag names to underscores for getattr
    if hasattr(args, "include_remote"):
        pass  # argparse already handles this with dest
    else:
        args.include_remote = False

    # Git version check (LO-1 fix)
    git_err = check_git_version()
    if git_err:
        print(json.dumps({"error": git_err}))
        sys.exit(1)

    # Resolve governance repo to absolute path
    args.governance_repo = str(Path(args.governance_repo).resolve())
    if not Path(args.governance_repo).is_dir():
        print(json.dumps({"error": f"Governance repo not found: {args.governance_repo}"}))
        sys.exit(1)

    dispatch = {
        "feature-state": cmd_feature_state,
        "branches": cmd_branches,
        "active-features": cmd_active_features,
    }

    result = dispatch[args.command](args)
    print(json.dumps(result, indent=2, default=str))

    # Exit 2 when discrepancies found (HO-2 fix)
    if args.command == "feature-state" and result.get("discrepancies"):
        sys.exit(2)


if __name__ == "__main__":
    main()
