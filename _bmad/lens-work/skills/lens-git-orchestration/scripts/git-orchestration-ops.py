#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML>=6.0"]
# ///
"""
git-orchestration-ops.py — Lens git write operations for the 3-branch control feature model.

Subcommands:
    create-feature-branches  Create {featureId} + {featureId}-plan + {featureId}-dev branches
  commit-artifacts         Stage and commit files with a structured message
  create-dev-branch        Create {featureId}-dev-{username} branch
    prepare-dev-branch       Prepare the target repo working branch for a dev cycle
  merge-plan               Merge {featureId}-plan into {featureId}
    publish-to-governance    Copy staged planning docs into governance docs path
    validate-phase-start     Validate branch topology/base branch/track before phase writes
    cleanup-branch           Delete merged step branch, switch to next branch, and pull
  push                     Push current (or named) branch to remote
    set-feature-base-branch  Set feature_base_branch in governance repo-inventory.yaml and commit+push

Exit codes:
  0 — success
  1 — hard error (precondition failed, git error, repo not found)
  2 — partial success with warnings
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


PHASE_ARTIFACTS: dict[str, list[str]] = {
    "preplan": ["product-brief", "research", "brainstorm"],
    "businessplan": ["prd", "ux-design"],
    "techplan": ["architecture", "review-report"],
    "finalizeplan": [
        "review-report",
        "epics",
        "stories",
        "implementation-readiness",
        "sprint-status",
        "story-files",
    ],
    "expressplan": [
        "business-plan",
        "tech-plan",
        "sprint-plan",
        "review-report",
    ],
}

DEV_BRANCH_MODES = ("direct-default", "feature-id", "feature-id-username")
SUPPORTED_TRACKS = {
    "quickplan",
    "full",
    "hotfix",
    "tech-change",
    "express",
    "expressplan",
    "standard",
    "spike",
}
TRACK_ALIASES = {
    "full": "standard",
    "tech-change": "standard",
    "quickplan": "express",
}

PHASE_ROUTE_TO_PLAN = {"preplan", "businessplan", "techplan", "expressplan"}


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git(args: list[str], cwd: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in the given directory."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        check=check,
        capture_output=capture,
        text=True,
    )


def check_git_version() -> str | None:
    """Return error string if git < 2.28, else None."""
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
        version_str = result.stdout.strip()
        parts = re.findall(r"(\d+)\.(\d+)", version_str)
        if parts:
            major, minor = int(parts[0][0]), int(parts[0][1])
            if (major, minor) < (2, 28):
                return f"git >= 2.28 required, found {version_str}"
    except FileNotFoundError:
        return "git not found on PATH"
    return None


def current_branch(repo: str) -> str:
    """Return name of current checked-out branch."""
    result = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    return result.stdout.strip()


def resolve_default_branch(repo: str, requested_branch: str | None = None) -> str:
    """Resolve the repo default branch, honoring an explicit override when given."""
    if requested_branch:
        return requested_branch

    result = git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], cwd=repo, check=False)
    if result.returncode == 0:
        remote_ref = result.stdout.strip()
        if remote_ref.startswith("origin/"):
            return remote_ref.removeprefix("origin/")

    for candidate in ("main", "master", "develop", "trunk"):
        if branch_exists(repo, candidate, include_remote=True):
            return candidate

    return current_branch(repo)


def branch_exists(repo: str, branch: str, include_remote: bool = False) -> bool:
    """Return True if branch exists locally (or remotely when include_remote=True)."""
    result = git(["branch", "--list", branch], cwd=repo)
    if result.stdout.strip():
        return True
    if include_remote:
        result = git(["branch", "-r", "--list", f"origin/{branch}"], cwd=repo)
        return bool(result.stdout.strip())
    return False


def has_tracking_ref(repo: str) -> bool:
    """Return True if current branch has an upstream tracking ref."""
    result = git(["rev-parse", "--abbrev-ref", "@{u}"], cwd=repo, check=False)
    return result.returncode == 0


def head_sha(repo: str) -> str:
    """Return short SHA of HEAD."""
    result = git(["rev-parse", "--short", "HEAD"], cwd=repo)
    return result.stdout.strip()


def verify_clean(repo: str) -> str | None:
    """Return error string if repo has uncommitted changes, else None."""
    result = git(["status", "--porcelain"], cwd=repo)
    if result.stdout.strip():
        return "working directory is not clean — commit or stash changes first"
    return None


def normalize_publish_path(path: Path) -> Path:
    """Normalize mixed-separator paths safely across platforms before publish operations."""
    return Path(os.path.normpath(str(path)))


def required_control_branches(feature_id: str) -> list[str]:
    """Return required control-branch topology for a feature."""
    return [feature_id, f"{feature_id}-plan", f"{feature_id}-dev"]


def missing_control_branches(repo: str, feature_id: str) -> list[str]:
    """Return missing control branches in the repo, checking local and remote refs."""
    missing: list[str] = []
    for branch in required_control_branches(feature_id):
        if not branch_exists(repo, branch, include_remote=True):
            missing.append(branch)
    return missing


def branch_for_phase_write(feature_id: str, phase: str | None, phase_step: str | None) -> tuple[str | None, str | None]:
    """Resolve the expected control-repo branch for a phase write."""
    normalized_phase = str(phase or "").strip().lower()
    normalized_step = str(phase_step or "").strip().lower()

    if normalized_phase == "dev":
        return None, "target_repo_only"

    if normalized_phase in PHASE_ROUTE_TO_PLAN:
        return f"{feature_id}-plan", "planning_or_express_to_plan"

    if normalized_phase == "finalizeplan":
        if normalized_step in {"step1", "step2", "1", "2", "finalizeplan-step1", "finalizeplan-step2"}:
            return f"{feature_id}-plan", "finalizeplan_step_1_2_to_plan"
        if normalized_step in {"step3", "3", "finalizeplan-step3"}:
            return feature_id, "finalizeplan_step_3_to_feature"
        return f"{feature_id}-plan", "finalizeplan_default_to_plan"

    return None, None


def canonical_track(track: str | None) -> str:
    normalized = str(track or "").strip().lower()
    return TRACK_ALIASES.get(normalized, normalized)


# ---------------------------------------------------------------------------
# feature.yaml helpers (shared with git-state-ops)
# ---------------------------------------------------------------------------

def find_feature_yaml(governance_repo: str, feature_id: str) -> Path | None:
    """Walk governance_repo looking for feature.yaml whose feature_id matches."""
    root = Path(governance_repo)
    for yaml_file in root.rglob("feature.yaml"):
        try:
            data = yaml.safe_load(yaml_file.read_text())
            if isinstance(data, dict) and (data.get("featureId") == feature_id or data.get("feature_id") == feature_id):
                return yaml_file
        except Exception:
            continue
    return None


def load_feature_yaml(path: Path) -> dict | None:
    """Load and parse a feature.yaml file. Returns None on parse error."""
    try:
        data = yaml.safe_load(path.read_text())
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def feature_identifier(data: dict) -> str | None:
    """Return the supported feature identifier from a feature.yaml payload."""
    return data.get("featureId") or data.get("feature_id")


def path_key(path: Path) -> str:
    """Return a normalized path key for cross-platform inventory comparisons."""
    return os.path.normcase(os.path.normpath(str(path.expanduser().resolve())))


def is_relative_to_path(path: Path, parent: Path) -> bool:
    """Return True when path is contained by parent after resolving both paths."""
    try:
        path.expanduser().resolve().relative_to(parent.expanduser().resolve())
        return True
    except ValueError:
        return False


def find_project_root_from_path(path: Path) -> Path | None:
    """Find the workspace root that owns TargetProjects for a repo/governance path."""
    current = path.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "TargetProjects").is_dir():
            return candidate
    return None


def resolve_inventory_local_path(local_path: str, *, project_root: Path, governance_repo: Path) -> Path:
    """Resolve a repo-inventory local_path using Lens workspace conventions."""
    raw_path = str(local_path or "").strip() or "."
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()

    normalized = raw_path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized == "TargetProjects" or normalized.startswith("TargetProjects/"):
        return (project_root / Path(normalized)).resolve()
    return (governance_repo / candidate).resolve()


def target_projects_inventory_entry(
    repo: str,
    governance_repo: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return the repo-inventory entry for a TargetProjects repo, or a structured error.

    Non-TargetProjects repos return ``(None, None)`` so existing control-repo PR
    flows continue to use their explicit branch arguments.
    """
    repo_path = Path(repo).expanduser().resolve()
    project_root = find_project_root_from_path(repo_path)
    if project_root is None:
        return None, None

    target_root = project_root / "TargetProjects"
    if not is_relative_to_path(repo_path, target_root):
        return None, None

    governance_path = Path(governance_repo).expanduser().resolve() if governance_repo else None
    if governance_path is None:
        inferred_governance = project_root / "TargetProjects" / "lens" / "lens-governance"
        if inferred_governance.exists():
            governance_path = inferred_governance.resolve()
        else:
            return None, {
                "status": "error",
                "error": "governance_repo_required",
                "detail": "TargetProjects repo branch policy requires --governance-repo so repo-inventory.yaml can be read.",
                "repo": str(repo_path),
                "action": "provide_governance_repo",
            }

    inventory_path = governance_path / "repo-inventory.yaml"
    if not inventory_path.exists():
        return None, {
            "status": "error",
            "error": "repo_inventory_not_found",
            "detail": "TargetProjects repo branch policy requires governance repo-inventory.yaml.",
            "repo": str(repo_path),
            "inventory_path": str(inventory_path),
        }

    try:
        inventory_data = yaml.safe_load(inventory_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return None, {
            "status": "error",
            "error": "repo_inventory_malformed",
            "detail": str(exc),
            "inventory_path": str(inventory_path),
        }

    repositories = inventory_data.get("repositories") or inventory_data.get("repos") or []
    if not isinstance(repositories, list):
        return None, {
            "status": "error",
            "error": "repo_inventory_malformed",
            "detail": "repo-inventory.yaml repositories must be a list.",
            "inventory_path": str(inventory_path),
        }

    repo_path_key = path_key(repo_path)
    for entry in repositories:
        if not isinstance(entry, dict):
            continue
        candidate_paths: list[str] = []
        primary = str(entry.get("local_path") or "").strip()
        if primary:
            candidate_paths.append(primary)
        extra_paths = entry.get("local_paths")
        if isinstance(extra_paths, list):
            candidate_paths.extend(str(p).strip() for p in extra_paths if str(p).strip())
        for local_path in candidate_paths:
            resolved_local_path = resolve_inventory_local_path(
                local_path,
                project_root=project_root,
                governance_repo=governance_path,
            )
            if path_key(resolved_local_path) == repo_path_key:
                return entry, None

    return None, {
        "status": "error",
        "error": "repo_inventory_entry_not_found",
        "detail": "TargetProjects repo is not registered in governance repo-inventory.yaml.",
        "repo": str(repo_path),
        "inventory_path": str(inventory_path),
        "action": "register_repo_inventory_entry",
    }


def feature_base_branch_missing_payload(repo: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Return the user-actionable error for missing TargetProjects base branch policy."""
    return {
        "status": "error",
        "error": "feature_base_branch_missing",
        "detail": "TargetProjects PRs must use repo-inventory.yaml feature_base_branch.",
        "repo": repo,
        "inventory_entry": entry.get("name") or entry.get("local_path") or "(unnamed)",
        "question": "What branch should PRs for this TargetProjects repo merge into?",
        "action": "ask_user_for_feature_base_branch",
        "next_step": "Call set-feature-base-branch --governance-repo <governance_repo> --repo <repo> --branch <answer> to persist the branch in repo-inventory.yaml, then retry.",
    }


def resolve_target_feature_base_branch(
    *,
    repo: str,
    governance_repo: str | None,
    requested_base_branch: str | None,
) -> tuple[str | None, dict[str, Any] | None, str | None]:
    """Resolve repo-inventory feature_base_branch for TargetProjects repos."""
    inventory_entry, inventory_error = target_projects_inventory_entry(repo, governance_repo)
    if inventory_error:
        return None, inventory_error, None
    if inventory_entry is None:
        return requested_base_branch, None, None

    feature_base_branch = str(inventory_entry.get("feature_base_branch") or "").strip()
    if not feature_base_branch:
        return None, feature_base_branch_missing_payload(repo, inventory_entry), None
    if requested_base_branch and requested_base_branch != feature_base_branch:
        return None, {
            "status": "error",
            "error": "feature_base_branch_mismatch",
            "detail": "TargetProjects PR base branch must match repo-inventory.yaml feature_base_branch.",
            "requested_base_branch": requested_base_branch,
            "feature_base_branch": feature_base_branch,
            "repo": repo,
            "inventory_entry": inventory_entry.get("name") or inventory_entry.get("local_path") or "(unnamed)",
        }, None
    return feature_base_branch, None, "repo-inventory.feature_base_branch"


def set_feature_base_branch_in_inventory(
    *,
    repo: str,
    governance_repo: str | None,
    branch: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Write feature_base_branch into the repo-inventory.yaml entry for repo.

    Returns ``(result_info, None)`` on success or ``(None, error_payload)`` on failure.
    The caller is responsible for committing and pushing the governance repo.
    """
    repo_path = Path(repo).expanduser().resolve()
    project_root = find_project_root_from_path(repo_path)
    if project_root is None:
        return None, {
            "status": "error",
            "error": "project_root_not_found",
            "detail": "Cannot find TargetProjects workspace root from repo path.",
            "repo": str(repo_path),
        }

    target_root = project_root / "TargetProjects"
    if not is_relative_to_path(repo_path, target_root):
        return None, {
            "status": "error",
            "error": "not_a_target_projects_repo",
            "detail": "Repo is not under TargetProjects — feature_base_branch is only tracked for TargetProjects repos.",
            "repo": str(repo_path),
        }

    governance_path = Path(governance_repo).expanduser().resolve() if governance_repo else None
    if governance_path is None:
        inferred_governance = project_root / "TargetProjects" / "lens" / "lens-governance"
        if inferred_governance.exists():
            governance_path = inferred_governance.resolve()
        else:
            return None, {
                "status": "error",
                "error": "governance_repo_required",
                "detail": "TargetProjects repo branch policy requires --governance-repo so repo-inventory.yaml can be written.",
                "repo": str(repo_path),
                "action": "provide_governance_repo",
            }

    inventory_path = governance_path / "repo-inventory.yaml"
    if not inventory_path.exists():
        return None, {
            "status": "error",
            "error": "repo_inventory_not_found",
            "detail": "Governance repo-inventory.yaml not found.",
            "repo": str(repo_path),
            "inventory_path": str(inventory_path),
        }

    try:
        inventory_data = yaml.safe_load(inventory_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return None, {
            "status": "error",
            "error": "repo_inventory_malformed",
            "detail": str(exc),
            "inventory_path": str(inventory_path),
        }

    data_key = "repositories" if "repositories" in inventory_data else "repos"
    repositories = inventory_data.get(data_key) or []
    if not isinstance(repositories, list):
        return None, {
            "status": "error",
            "error": "repo_inventory_malformed",
            "detail": "repo-inventory.yaml repositories must be a list.",
            "inventory_path": str(inventory_path),
        }

    repo_path_key = path_key(repo_path)
    entry_index: int | None = None
    for i, entry in enumerate(repositories):
        if not isinstance(entry, dict):
            continue
        candidate_paths: list[str] = []
        primary = str(entry.get("local_path") or "").strip()
        if primary:
            candidate_paths.append(primary)
        extra_paths = entry.get("local_paths")
        if isinstance(extra_paths, list):
            candidate_paths.extend(str(p).strip() for p in extra_paths if str(p).strip())
        for local_path in candidate_paths:
            resolved_local_path = resolve_inventory_local_path(
                local_path,
                project_root=project_root,
                governance_repo=governance_path,
            )
            if path_key(resolved_local_path) == repo_path_key:
                entry_index = i
                break
        if entry_index is not None:
            break

    if entry_index is None:
        return None, {
            "status": "error",
            "error": "repo_inventory_entry_not_found",
            "detail": "TargetProjects repo is not registered in governance repo-inventory.yaml.",
            "repo": str(repo_path),
            "inventory_path": str(inventory_path),
            "action": "register_repo_inventory_entry",
        }

    entry_name = repositories[entry_index].get("name") or repositories[entry_index].get("local_path") or "(unnamed)"
    repositories[entry_index]["feature_base_branch"] = branch
    inventory_data[data_key] = repositories
    inventory_path.write_text(yaml.safe_dump(inventory_data, sort_keys=False), encoding="utf-8")

    return {
        "inventory_path": str(inventory_path),
        "governance_repo": str(governance_path),
        "repo": str(repo_path),
        "entry_name": entry_name,
        "feature_base_branch": branch,
    }, None


def cmd_set_feature_base_branch(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Set feature_base_branch in repo-inventory.yaml, then commit and push from governance repo."""
    repo = args.repo
    governance_repo = args.governance_repo
    branch = (args.branch or "").strip()

    if not branch:
        return {"status": "error", "error": "branch_required", "detail": "--branch is required."}, 1

    write_result, write_error = set_feature_base_branch_in_inventory(
        repo=repo,
        governance_repo=governance_repo,
        branch=branch,
    )
    if write_error:
        return write_error, 1

    inventory_path = write_result["inventory_path"]
    governance_path = write_result["governance_repo"]
    entry_name = write_result["entry_name"]
    commit_msg = f"chore(repo-inventory): set feature_base_branch={branch} for {entry_name}"

    runner = Runner(args.dry_run, governance_path)
    try:
        runner.run(["add", inventory_path])
    except RuntimeError as exc:
        return {"status": "error", "error": "stage_failed", "detail": str(exc)}, 1

    if not args.dry_run:
        staged_check = git(["diff", "--cached", "--quiet"], cwd=governance_path, check=False)
        if staged_check.returncode == 0:
            return {
                "status": "pass",
                "repo": repo,
                "entry_name": entry_name,
                "feature_base_branch": branch,
                "inventory_path": inventory_path,
                "committed": False,
                "pushed": False,
                "note": "feature_base_branch already set to this value — nothing to commit",
                "dry_run": args.dry_run,
            }, 0

    try:
        runner.run(["commit", "-m", commit_msg])
    except RuntimeError as exc:
        return {"status": "error", "error": "commit_failed", "detail": str(exc)}, 1

    try:
        if args.dry_run:
            runner.run(["push"])
        elif has_tracking_ref(governance_path):
            runner.run(["push"])
        else:
            current = current_branch(governance_path)
            runner.run(["push", "--set-upstream", "origin", current])
    except RuntimeError as exc:
        detail = str(exc)
        if "rejected" in detail:
            return {"status": "error", "error": "push_rejected", "detail": detail}, 1
        if "authentication" in detail.lower() or "403" in detail:
            return {"status": "error", "error": "auth_failed", "detail": detail}, 1
        return {"status": "error", "error": "push_failed", "detail": detail}, 1

    sha = head_sha(governance_path) if not args.dry_run else "dry-run"
    return {
        "status": "pass",
        "repo": repo,
        "entry_name": entry_name,
        "feature_base_branch": branch,
        "inventory_path": inventory_path,
        "commit_message": commit_msg,
        "commit_sha": sha,
        "committed": True,
        "pushed": not args.dry_run,
        "dry_run": args.dry_run,
    }, 0


def resolve_docs_roots(control_repo: str, governance_repo: str, feature_data: dict, feature_id: str) -> tuple[Path, Path]:
    """Resolve control staging and governance mirror directories for feature docs."""
    domain = feature_data.get("domain", "")
    service = feature_data.get("service", "")
    docs_data = feature_data.get("docs") or {}

    control_rel = docs_data.get("path") or f"docs/{domain}/{service}/{feature_id}"
    governance_rel = docs_data.get("governance_docs_path") or f"features/{domain}/{service}/{feature_id}/docs"

    return Path(control_repo) / control_rel, Path(governance_repo) / governance_rel


def artifact_candidates(docs_root: Path, name: str, phase: str | None = None) -> list[Path]:
    """Return candidate files for a named lifecycle artifact."""
    match name:
        case "product-brief":
            candidates = [docs_root / "product-brief.md"]
            candidates += list(docs_root.glob("product-brief-*.md"))
        case "research":
            candidates = [docs_root / "research.md"]
            candidates += list(docs_root.glob("research-*.md"))
            candidates += list((docs_root / "research").glob("*.md"))
        case "brainstorm":
            candidates = [docs_root / "brainstorm.md"]
        case "prd":
            candidates = [docs_root / "prd.md"]
        case "ux-design":
            candidates = [docs_root / "ux-design.md", docs_root / "ux-design-specification.md"]
        case "architecture":
            candidates = [docs_root / "architecture.md"]
            candidates += list(docs_root.glob("*architecture*.md"))
        case "business-plan":
            candidates = [docs_root / "business-plan.md"]
        case "tech-plan":
            candidates = [docs_root / "tech-plan.md"]
        case "sprint-plan":
            candidates = [docs_root / "sprint-plan.md"]
        case "epics":
            candidates = [docs_root / "epics.md"]
        case "stories":
            candidates = [docs_root / "stories.md"]
        case "implementation-readiness":
            candidates = [docs_root / "readiness-checklist.md", docs_root / "implementation-readiness.md"]
        case "sprint-status":
            candidates = [docs_root / "sprint-status.yaml", docs_root / "sprint-backlog.md"]
        case "story-files":
            candidates = story_file_candidates(docs_root)
        case "review-report":
            if (phase or "").strip().lower() == "expressplan":
                candidates = [
                    docs_root / "expressplan-adversarial-review.md",
                    docs_root / "expressplan-review.md",
                ]
            else:
                candidates = [
                    docs_root / "review-report.md",
                    docs_root / "adversarial-review.md",
                    docs_root / "preplan-adversarial-review.md",
                    docs_root / "businessplan-adversarial-review.md",
                    docs_root / "techplan-adversarial-review.md",
                    docs_root / "expressplan-adversarial-review.md",
                    docs_root / "finalizeplan-review.md",
                ]
        case _:
            candidates = [docs_root / f"{name}.md"]
    return candidates


def story_file_candidates(docs_root: Path) -> list[Path]:
    """Return supported story file shapes from the staged docs root."""
    candidates: list[Path] = []
    seen: set[Path] = set()

    for pattern in ("dev-story-*.md", "dev-story-*.yaml", "[0-9]*-[0-9]*-*.md", "[0-9]*-[0-9]*-*.yaml"):
        for candidate in docs_root.glob(pattern):
            if candidate not in seen:
                candidates.append(candidate)
                seen.add(candidate)

    stories_dir = docs_root / "stories"
    if stories_dir.exists():
        for pattern in ("*.md", "*.yaml"):
            for candidate in stories_dir.glob(pattern):
                if candidate not in seen:
                    candidates.append(candidate)
                    seen.add(candidate)

    return candidates


def existing_artifact_files(docs_root: Path, artifact_name: str, phase: str | None = None) -> list[Path]:
    """Return existing non-empty files for an artifact name."""
    return [
        candidate
        for candidate in artifact_candidates(docs_root, artifact_name, phase=phase)
        if candidate.exists() and candidate.stat().st_size > 0
    ]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def validate_slug(value: str, field_name: str = "value") -> str | None:
    """Return error string if value is not a valid slug, else None."""
    if not _SLUG_RE.match(value):
        return f"invalid {field_name} '{value}' — must be lowercase alphanumeric + hyphens, no leading/trailing hyphens, no slashes"
    return None


def build_dev_branch_name(
    feature_id: str,
    mode: str,
    username: str | None = None,
    feature_slug: str | None = None,
) -> str:
    """Return the target-repo working branch for a repo-scoped dev mode."""
    normalized_mode = (mode or "").strip().lower()
    branch_slug = feature_slug or feature_id
    if normalized_mode == "direct-default":
        return ""
    if normalized_mode == "feature-id":
        return f"feature/{branch_slug}"
    if normalized_mode == "feature-id-username":
        if not username:
            raise ValueError("username is required for mode 'feature-id-username'")
        return f"feature/{branch_slug}-{username}"
    expected = ", ".join(DEV_BRANCH_MODES)
    raise ValueError(f"invalid mode '{mode}' — expected one of: {expected}")


# ---------------------------------------------------------------------------
# dry-run runner
# ---------------------------------------------------------------------------

class Runner:
    def __init__(self, dry_run: bool, repo: str):
        self.dry_run = dry_run
        self.repo = repo
        self.log: list[str] = []

    def run(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd_str = "git " + " ".join(args)
        if self.dry_run:
            print(f"[dry-run] {cmd_str}", file=sys.stderr)
            self.log.append(cmd_str)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        result = git(args, cwd=self.repo, check=False)
        if result.returncode != 0:
            # Include both stdout and stderr — git writes CONFLICT lines to stdout
            combined = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
            raise RuntimeError(f"git {args[0]} failed: {combined}")
        return result


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_create_feature_branches(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    feature_id = args.feature_id
    governance_repo = args.governance_repo
    repo = args.repo or governance_repo
    default_branch = resolve_default_branch(repo, args.default_branch)

    err = validate_slug(feature_id, "feature_id")
    if err:
        return {"error": "invalid_feature_id", "detail": err}, 1

    yaml_path = find_feature_yaml(governance_repo, feature_id)
    if yaml_path is None:
        return {"error": "feature_yaml_not_found", "feature_id": feature_id}, 1

    plan_branch = f"{feature_id}-plan"
    dev_branch = f"{feature_id}-dev"

    if branch_exists(repo, feature_id, include_remote=True):
        return {"error": "branch_already_exists", "branch": feature_id}, 1
    if branch_exists(repo, plan_branch, include_remote=True):
        return {"error": "branch_already_exists", "branch": plan_branch}, 1
    if branch_exists(repo, dev_branch, include_remote=True):
        return {"error": "branch_already_exists", "branch": dev_branch}, 1

    # Precondition: working directory must be clean before switching branches
    if not args.dry_run:
        dirty = verify_clean(repo)
        if dirty:
            return {"error": "dirty_working_tree", "detail": dirty}, 1

    runner = Runner(args.dry_run, repo)
    saved = current_branch(repo)
    try:
        runner.run(["checkout", default_branch])
        try:
            runner.run(["pull", "origin", default_branch])
        except RuntimeError as exc:
            return {"error": "pull_failed", "detail": str(exc)}, 1
        runner.run(["checkout", "-b", feature_id])
        runner.run(["push", "--set-upstream", "origin", feature_id])
        runner.run(["checkout", "-b", plan_branch])
        runner.run(["push", "--set-upstream", "origin", plan_branch])
        runner.run(["checkout", "-b", dev_branch])
        runner.run(["push", "--set-upstream", "origin", dev_branch])
    except RuntimeError as exc:
        return {"error": "push_failed", "detail": str(exc)}, 1
    finally:
        git(["checkout", saved], cwd=repo, check=False)

    return {
        "feature_id": feature_id,
        "base_branch": feature_id,
        "plan_branch": plan_branch,
        "dev_branch": dev_branch,
        "base_remote": f"origin/{feature_id}",
        "plan_remote": f"origin/{plan_branch}",
        "dev_remote": f"origin/{dev_branch}",
        "created_from": default_branch,
        "target_repo_branch_modes": list(DEV_BRANCH_MODES),
        "dry_run": args.dry_run,
    }, 0


def cmd_commit_artifacts(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo = args.repo
    feature_id = args.feature_id
    files = args.files
    description = getattr(args, "description", None)
    message = getattr(args, "message", None)
    if description and message and description != message:
        return {
            "error": "conflicting_message_aliases",
            "detail": "--description and --message must match when both are provided.",
        }, 1
    description = description or message
    if not description:
        return {"error": "description_missing", "detail": "Provide --description or --message."}, 1
    push = args.push

    if not files:
        return {"error": "no_files_specified"}, 1

    root = Path(repo)
    for f in files:
        if not (root / f).exists():
            return {"error": "file_not_found", "path": f}, 1

    # Guard: control topology must exist before phase writes begin.
    if not args.dry_run:
        missing = missing_control_branches(repo, feature_id)
        if missing:
            return {
                "error": "missing_required_branch",
                "feature_id": feature_id,
                "missing_branches": missing,
                "action": "init-feature",
                "detail": "Required control branches are missing. Re-run init-feature/create-feature-branches.",
            }, 1

    # Resolve effective phase (args.phase if provided, else from feature.yaml)
    phase = args.phase
    warnings: list[str] = []
    if not phase:
        governance_repo = args.governance_repo or repo
        yaml_path = find_feature_yaml(governance_repo, feature_id)
        if yaml_path:
            data = load_feature_yaml(yaml_path)
            if data:
                phase = data.get("phase")
        if not phase:
            phase = "unknown"
            warnings.append("phase could not be resolved from feature.yaml — defaulted to 'unknown'")

    # Guard: must be on a branch belonging to this feature
    if not args.dry_run:
        cb = current_branch(repo)
        allowed = {feature_id, f"{feature_id}-plan", f"{feature_id}-dev"}
        if cb not in allowed and not cb.startswith(f"{feature_id}-dev-"):
            return {
                "error": "wrong_branch",
                "current": cb,
                "expected": [feature_id, f"{feature_id}-plan", f"{feature_id}-dev", f"{feature_id}-dev-<username>"],
            }, 1

        expected_branch, routing_rule = branch_for_phase_write(feature_id, phase, getattr(args, "phase_step", None))
        routing_decision: dict[str, Any] = {
            "phase": phase,
            "phase_step": getattr(args, "phase_step", None),
            "current_branch": cb,
            "expected_branch": expected_branch,
            "routing_rule": routing_rule,
            "routing_enforced": True,
        }
        if routing_rule == "target_repo_only":
            return {
                "error": "target_repo_only_phase",
                "detail": "Dev artifacts must be committed in the target repo, not control-repo branches.",
                "routing": routing_decision,
            }, 1
        if expected_branch and cb != expected_branch:
            return {
                "status": "error",
                "error": "branch_mismatch",
                "current_branch": cb,
                "expected_branch": expected_branch,
                "detail": (
                    f"Phase '{phase}' step '{getattr(args, 'phase_step', None) or ''}' requires branch "
                    f"'{expected_branch}'. Currently on '{cb}'. Checkout '{expected_branch}' before committing."
                ),
                "routing": routing_decision,
            }, 1
    else:
        routing_decision = {
            "phase": phase,
            "phase_step": getattr(args, "phase_step", None),
            "current_branch": "(dry-run)",
            "expected_branch": branch_for_phase_write(feature_id, phase, getattr(args, "phase_step", None))[0],
            "routing_rule": branch_for_phase_write(feature_id, phase, getattr(args, "phase_step", None))[1],
            "routing_enforced": True,
        }

    commit_msg = f"[{phase}] {feature_id} — {description}"

    # Confirmation step: print staged files and ask unless --no-confirm is set
    if not args.no_confirm and not args.dry_run:
        print(f"Files to be staged and committed:", file=sys.stderr)
        for f in files:
            print(f"  {f}", file=sys.stderr)
        print(f"Commit message: {commit_msg}", file=sys.stderr)
        print("Proceed? [y/N] ", end="", flush=True, file=sys.stderr)
        answer = sys.stdin.readline().strip().lower()
        if answer not in ("y", "yes"):
            return {"error": "cancelled", "reason": "user declined confirmation"}, 1

    runner = Runner(args.dry_run, repo)
    try:
        runner.run(["add"] + list(files))
    except RuntimeError as exc:
        return {"error": "stage_failed", "detail": str(exc)}, 1

    # Check nothing to commit (inspect the index directly, not working-tree status)
    if not args.dry_run:
        staged_check = git(["diff", "--cached", "--quiet"], cwd=repo, check=False)
        if staged_check.returncode == 0:
            return {"error": "nothing_to_commit"}, 1
        if staged_check.returncode != 1:
            return {
                "error": "nothing_to_commit_check_failed",
                "detail": (staged_check.stderr or staged_check.stdout).strip(),
            }, 1

    try:
        runner.run(["commit", "-m", commit_msg])
    except RuntimeError as exc:
        return {"error": "commit_failed", "detail": str(exc)}, 1

    sha = head_sha(repo) if not args.dry_run else "dry-run"

    if push:
        try:
            runner.run(["push"])
        except RuntimeError as exc:
            return {"error": "push_failed", "detail": str(exc)}, 1

    result: dict[str, Any] = {
        "feature_id": feature_id,
        "branch": current_branch(repo) if not args.dry_run else "(dry-run)",
        "phase": phase,
        "files_committed": list(files),
        "commit_sha": sha,
        "commit_message": commit_msg,
        "pushed": push and not args.dry_run,
        "routing": routing_decision,
        "dry_run": args.dry_run,
    }
    if warnings:
        result["warnings"] = warnings
    return result, 0


def cmd_create_dev_branch(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    feature_id = args.feature_id
    username = args.username
    repo = args.repo or args.governance_repo

    err = validate_slug(username, "username")
    if err:
        return {"error": "invalid_username", "detail": err}, 1

    if not branch_exists(repo, feature_id):
        return {"error": "base_branch_not_found", "branch": feature_id}, 1

    dev_branch = f"{feature_id}-dev-{username}"
    if branch_exists(repo, dev_branch, include_remote=True):
        return {"error": "branch_already_exists", "branch": dev_branch}, 1

    runner = Runner(args.dry_run, repo)
    saved = current_branch(repo)
    try:
        runner.run(["checkout", feature_id])
        runner.run(["checkout", "-b", dev_branch])
        runner.run(["push", "--set-upstream", "origin", dev_branch])
    except RuntimeError as exc:
        return {"error": "push_failed", "detail": str(exc)}, 1
    finally:
        git(["checkout", saved], cwd=repo, check=False)

    return {
        "feature_id": feature_id,
        "dev_branch": dev_branch,
        "parent_branch": feature_id,
        "remote": f"origin/{dev_branch}",
        "dry_run": args.dry_run,
    }, 0


def cmd_prepare_dev_branch(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo = args.repo
    feature_id = args.feature_id
    feature_slug = getattr(args, "feature_slug", None)
    mode = (args.mode or "").strip().lower()
    username = getattr(args, "username", None)

    err = validate_slug(feature_id, "feature_id")
    if err:
        return {"error": "invalid_feature_id", "detail": err}, 1
    if feature_slug:
        slug_err = validate_slug(feature_slug, "feature_slug")
        if slug_err:
            return {"error": "invalid_feature_slug", "detail": slug_err}, 1
    if mode == "feature-id-username":
        username_err = validate_slug(username or "", "username")
        if username_err:
            return {"error": "invalid_username", "detail": username_err}, 1
    elif mode not in DEV_BRANCH_MODES:
        expected = ", ".join(DEV_BRANCH_MODES)
        return {"error": "invalid_mode", "detail": f"invalid mode '{args.mode}' — expected one of: {expected}"}, 1

    feature_base_branch, feature_base_error, base_branch_source = resolve_target_feature_base_branch(
        repo=repo,
        governance_repo=getattr(args, "governance_repo", None),
        requested_base_branch=args.base_branch,
    )
    if feature_base_error:
        return feature_base_error, 1
    default_branch = resolve_default_branch(repo, feature_base_branch)
    if not args.dry_run:
        dirty = verify_clean(repo)
        if dirty:
            return {"error": "dirty_working_tree", "detail": dirty}, 1

    runner = Runner(args.dry_run, repo)

    try:
        runner.run(["checkout", default_branch])
        try:
            runner.run(["pull", "origin", default_branch])
        except RuntimeError as exc:
            return {"error": "pull_failed", "detail": str(exc)}, 1
    except RuntimeError as exc:
        return {"error": "prepare_branch_failed", "detail": str(exc)}, 1

    if mode == "direct-default":
        return {
            "feature_id": feature_id,
            "feature_slug": feature_slug or feature_id,
            "mode": mode,
            "base_branch": default_branch,
            "base_branch_source": base_branch_source,
            "working_branch": default_branch,
            "created": False,
            "reused": True,
            "pushed": False,
            "requires_pr": False,
            "dry_run": args.dry_run,
        }, 0

    working_branch = build_dev_branch_name(feature_id, mode, username, feature_slug=feature_slug)
    local_exists = branch_exists(repo, working_branch)
    remote_exists = branch_exists(repo, working_branch, include_remote=True)
    created = False
    reused = False
    pushed = False

    try:
        if local_exists:
            runner.run(["checkout", working_branch])
            if not args.dry_run and has_tracking_ref(repo):
                runner.run(["pull"])
            elif remote_exists and not args.dry_run:
                runner.run(["branch", "--set-upstream-to", f"origin/{working_branch}", working_branch])
                runner.run(["pull", "origin", working_branch])
            reused = True
        elif remote_exists:
            runner.run(["checkout", "-b", working_branch, f"origin/{working_branch}"])
            reused = True
        else:
            runner.run(["checkout", "-b", working_branch])
            runner.run(["push", "--set-upstream", "origin", working_branch])
            created = True
            pushed = True
    except RuntimeError as exc:
        return {"error": "prepare_branch_failed", "detail": str(exc)}, 1

    return {
        "feature_id": feature_id,
        "feature_slug": feature_slug or feature_id,
        "mode": mode,
        "base_branch": default_branch,
        "base_branch_source": base_branch_source,
        "working_branch": working_branch,
        "created": created,
        "reused": reused,
        "pushed": pushed,
        "requires_pr": True,
        "pr_base_branch": default_branch,
        "dry_run": args.dry_run,
    }, 0


def _run_gh(repo: str, args: list[str]) -> tuple[subprocess.CompletedProcess | None, dict[str, Any] | None]:
    """Run a gh command and normalize not-found handling."""
    try:
        return subprocess.run(
            ["gh"] + args,
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        ), None
    except FileNotFoundError:
        return None, {"error": "gh_not_found", "detail": "gh CLI not found on PATH"}


def _gh_auth_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(token in lowered for token in ["authentication", "not logged", "login required", "403"])


def resolve_git_ref(repo: str, branch: str) -> str | None:
    """Resolve a branch name to a local or origin ref for git plumbing calls, preferring origin/ when available.

    The remote check (``git branch -r``) is intentionally separate from the
    local check via ``branch_exists()`` so that the remote ref is returned
    whenever possible, ensuring merge-base computations use the most current
    authoritative state rather than a potentially stale local copy.
    """
    remote_result = git(["branch", "-r", "--list", f"origin/{branch}"], cwd=repo, check=False)
    if remote_result.stdout.strip():
        return f"origin/{branch}"
    if branch_exists(repo, branch):
        return branch
    return None


def _default_base_candidates(repo: str) -> tuple[str, ...]:
    """Return a deduplicated ordered tuple of base-branch candidates for *repo*.

    The list begins with the branch detected via ``resolve_default_branch``
    (which probes ``origin/HEAD``) so repos whose primary branch is named
    anything other than ``main`` / ``develop`` are handled correctly.  The
    remaining well-known names are appended as fall-back entries.
    """
    detected = resolve_default_branch(repo)
    return tuple(dict.fromkeys([detected, "main", "master", "develop", "trunk"]))


def merge_base_sha(repo: str, head_ref: str, base_ref: str) -> str | None:
    """Return merge-base SHA for refs, or None when no shared history exists."""
    result = git(["merge-base", head_ref, base_ref], cwd=repo, check=False)
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def merge_base_timestamp(repo: str, merge_base: str) -> int:
    """Return commit timestamp (epoch seconds) for a merge-base SHA, or -1 on failure."""
    result = git(["log", "-1", "--format=%ct", merge_base], cwd=repo, check=False)
    if result.returncode != 0:
        return -1
    try:
        return int(result.stdout.strip())
    except ValueError:
        return -1


def pick_base_branch(repo: str, head_branch: str, candidates: tuple[str, ...] | None = None) -> str | None:
    """Return the candidate branch whose merge-base with head is most recent.

    When *candidates* is omitted the function uses :func:`_default_base_candidates`
    to build a deduplicated list starting with the repo's detected default branch
    so that repos using any naming convention (main, master, develop, trunk) are
    covered.
    """
    if candidates is None:
        candidates = _default_base_candidates(repo)

    head_ref = resolve_git_ref(repo, head_branch)
    if head_ref is None:
        return None

    best_branch: str | None = None
    best_ts = -1
    for candidate in candidates:
        candidate_ref = resolve_git_ref(repo, candidate)
        if candidate_ref is None:
            continue
        merge_base = merge_base_sha(repo, head_ref, candidate_ref)
        if not merge_base:
            continue
        ts = merge_base_timestamp(repo, merge_base)
        if ts > best_ts:
            best_ts = ts
            best_branch = candidate

    return best_branch


def _ensure_pull_request(
    repo: str,
    *,
    base_branch: str,
    head_branch: str,
    title: str,
    body: str,
    auto_merge: bool,
    dry_run: bool,
) -> tuple[dict[str, Any], int]:
    """Create or reuse a PR, optionally enabling auto-merge."""
    payload: dict[str, Any] = {
        "base_branch": base_branch,
        "head_branch": head_branch,
        "auto_merge_requested": auto_merge,
    }

    if dry_run:
        payload.update({
            "pr_url": "(dry-run)",
            "created": None,
            "auto_merge_enabled": None if auto_merge else False,
        })
        return payload, 0

    list_result, list_error = _run_gh(
        repo,
        [
            "pr",
            "list",
            "--head",
            head_branch,
            "--base",
            base_branch,
            "--state",
            "open",
            "--json",
            "url,autoMergeRequest",
        ],
    )
    if list_error:
        return list_error, 1
    if list_result is None:
        return {"error": "pr_lookup_failed", "detail": "gh returned no result"}, 1
    if list_result.returncode != 0:
        detail = list_result.stderr.strip() or list_result.stdout.strip()
        if _gh_auth_error(detail):
            return {"error": "gh_not_authenticated", "detail": detail}, 1
        return {"error": "pr_lookup_failed", "detail": detail}, 1

    try:
        existing_prs = json.loads(list_result.stdout or "[]")
    except json.JSONDecodeError as exc:
        return {"error": "pr_lookup_failed", "detail": f"invalid gh json: {exc}"}, 1

    existing = existing_prs[0] if existing_prs else None
    if existing:
        payload.update({
            "pr_url": existing.get("url", ""),
            "created": False,
            "auto_merge_enabled": bool(existing.get("autoMergeRequest")),
        })
    else:
        create_result, create_error = _run_gh(
            repo,
            [
                "pr",
                "create",
                "--base",
                base_branch,
                "--head",
                head_branch,
                "--title",
                title,
                "--body",
                body,
            ],
        )
        if create_error:
            return create_error, 1
        if create_result is None:
            return {"error": "pr_create_failed", "detail": "gh returned no result"}, 1
        if create_result.returncode != 0:
            detail = create_result.stderr.strip() or create_result.stdout.strip()
            if _gh_auth_error(detail):
                return {"error": "gh_not_authenticated", "detail": detail}, 1
            return {"error": "pr_create_failed", "detail": detail}, 1
        payload.update({
            "pr_url": create_result.stdout.strip(),
            "created": True,
            "auto_merge_enabled": False,
        })

    exit_code = 0
    if auto_merge and not payload.get("auto_merge_enabled"):
        merge_result, merge_error = _run_gh(
            repo,
            ["pr", "merge", payload["pr_url"], "--auto", "--merge"],
        )
        if merge_error:
            payload["warnings"] = [merge_error["detail"]]
            return payload, 2
        if merge_result is None:
            payload["warnings"] = ["gh returned no result while enabling auto-merge"]
            return payload, 2
        if merge_result.returncode != 0:
            detail = merge_result.stderr.strip() or merge_result.stdout.strip()
            payload["warnings"] = [f"auto_merge_not_enabled: {detail}"]
            return payload, 2
        payload["auto_merge_enabled"] = True

    return payload, exit_code


def cmd_create_pr(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo = args.repo or args.governance_repo
    head_branch = getattr(args, "head", None)
    source_branch = getattr(args, "source_branch", None)
    if head_branch and source_branch and head_branch != source_branch:
        return {
            "status": "error",
            "error": "conflicting_branch_aliases",
            "detail": "--head and --source-branch must match when both are provided.",
            "head": head_branch,
            "source_branch": source_branch,
        }, 1
    head_branch = head_branch or source_branch
    if not head_branch:
        return {
            "status": "error",
            "error": "head_branch_missing",
            "detail": "Provide --head or --source-branch.",
        }, 1

    explicit_base = getattr(args, "base", None)
    target_branch = getattr(args, "target_branch", None)
    if explicit_base and target_branch and explicit_base != target_branch:
        return {
            "status": "error",
            "error": "conflicting_branch_aliases",
            "detail": "--base and --target-branch must match when both are provided.",
            "base": explicit_base,
            "target_branch": target_branch,
        }, 1
    explicit_base = explicit_base or target_branch
    auto_detect_base = bool(getattr(args, "auto_detect_base", False))

    inventory_base_branch, inventory_base_error, base_branch_source = resolve_target_feature_base_branch(
        repo=repo,
        governance_repo=args.governance_repo,
        requested_base_branch=explicit_base,
    )
    if inventory_base_error:
        return inventory_base_error, 1
    if base_branch_source:
        explicit_base = inventory_base_branch
        auto_detect_base = False

    if not branch_exists(repo, head_branch, include_remote=True):
        return {"error": "head_branch_not_found", "branch": head_branch}, 1

    if explicit_base and not branch_exists(repo, explicit_base, include_remote=True):
        return {"error": "base_branch_not_found", "branch": explicit_base}, 1

    if auto_detect_base or not explicit_base:
        auto_candidates = _default_base_candidates(repo)
        resolved_base = pick_base_branch(repo, head_branch, candidates=auto_candidates)
        if resolved_base is None:
            return {
                "status": "error",
                "error": "no_common_ancestor",
                "detail": f"No shared history found between '{head_branch}' and any candidate base branch.",
                "head_branch": head_branch,
                "candidates_checked": list(auto_candidates),
            }, 1
        base_branch = resolved_base
    else:
        head_ref = resolve_git_ref(repo, head_branch)
        base_ref = resolve_git_ref(repo, explicit_base)
        if not head_ref or not base_ref or not merge_base_sha(repo, head_ref, base_ref):
            return {
                "status": "error",
                "error": "no_common_ancestor",
                "detail": f"No shared history found between head '{head_branch}' and base '{explicit_base}'.",
            }, 1
        base_branch = explicit_base

    result_payload: dict[str, Any] = {
        "strategy": "pr",
        "base_branch": base_branch,
        "base_branch_source": base_branch_source,
        "head_branch": head_branch,
        "dry_run": args.dry_run,
    }

    pr_payload, exit_code = _ensure_pull_request(
        repo,
        base_branch=base_branch,
        head_branch=head_branch,
        title=args.title or f"[pr] {head_branch} — merge into {base_branch}",
        body=args.body,
        auto_merge=args.auto_merge,
        dry_run=args.dry_run,
    )
    if "error" in pr_payload:
        return pr_payload, exit_code
    result_payload.update(pr_payload)
    return result_payload, exit_code


def cmd_merge_plan(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    feature_id = args.feature_id
    repo = args.repo or args.governance_repo
    strategy = args.strategy
    delete_after = args.delete_after_merge

    plan_branch = f"{feature_id}-plan"

    if not branch_exists(repo, feature_id):
        return {"error": "base_branch_not_found", "branch": feature_id}, 1
    if not branch_exists(repo, plan_branch):
        return {"error": "plan_branch_not_found", "branch": plan_branch}, 1

    missing = missing_control_branches(repo, feature_id)
    if missing:
        return {
            "error": "missing_required_branch",
            "feature_id": feature_id,
            "missing_branches": missing,
            "action": "init-feature",
            "detail": "Required control branches are missing. Re-run init-feature/create-feature-branches.",
        }, 1

    result_payload: dict[str, Any] = {
        "feature_id": feature_id,
        "strategy": strategy,
        "base_branch": feature_id,
        "plan_branch": plan_branch,
        "plan_branch_deleted": False,
        "auto_merge_requested": bool(getattr(args, "auto_merge", False)),
        "dry_run": args.dry_run,
    }

    runner = Runner(args.dry_run, repo)

    if strategy == "pr":
        pr_payload, exit_code = _ensure_pull_request(
            repo,
            base_branch=feature_id,
            head_branch=plan_branch,
            title=f"[plan] {feature_id} — merge planning artifacts",
            body="Auto-created by lens-git-orchestration",
            auto_merge=getattr(args, "auto_merge", False),
            dry_run=args.dry_run,
        )
        if "error" in pr_payload:
            return pr_payload, exit_code
        result_payload.update(pr_payload)
        return result_payload, exit_code
    else:  # direct
        # Guard: clean working tree before checkout
        dirty = verify_clean(repo) if not args.dry_run else None
        if dirty:
            return {"error": "dirty_working_tree", "detail": dirty}, 1

        saved = current_branch(repo)
        merge_started = False
        try:
            runner.run(["checkout", feature_id])
            merge_started = True
            runner.run(["merge", "--no-ff", plan_branch, "-m", f"[merge] {feature_id} — merge plan into base"])
            merge_started = False
            # Push: use --set-upstream if no tracking ref exists
            if not args.dry_run and not has_tracking_ref(repo):
                runner.run(["push", "--set-upstream", "origin", feature_id])
            else:
                runner.run(["push"])
            if delete_after:
                runner.run(["branch", "-d", plan_branch])
                runner.run(["push", "origin", "--delete", plan_branch])
                result_payload["plan_branch_deleted"] = True
        except RuntimeError as exc:
            detail = str(exc)
            if merge_started:
                # Conflict — abort to restore clean state, then restore branch
                git(["merge", "--abort"], cwd=repo, check=False)
                merge_started = False
            if "CONFLICT" in detail or "conflict" in detail.lower() or "Automatic merge failed" in detail:
                git(["checkout", saved], cwd=repo, check=False)
                return {"error": "merge_conflict", "detail": detail}, 1
            return {"error": "push_failed", "detail": detail}, 1
        finally:
            restore = git(["checkout", saved], cwd=repo, check=False)
            if restore.returncode != 0 and not args.dry_run:
                result_payload["warnings"] = [f"branch restore failed — still on {feature_id}"]

    return result_payload, 0


def cmd_push(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo = args.repo or args.governance_repo
    branch = args.branch or current_branch(repo)

    # Precondition: verify origin remote is configured
    if not args.dry_run:
        remote_check = git(["remote", "get-url", "origin"], cwd=repo, check=False)
        if remote_check.returncode != 0:
            return {"error": "remote_not_found", "remote": "origin"}, 1

    runner = Runner(args.dry_run, repo)
    tracking = has_tracking_ref(repo) if not args.dry_run else False

    try:
        if tracking:
            runner.run(["push"])
        else:
            runner.run(["push", "--set-upstream", "origin", branch])
    except RuntimeError as exc:
        detail = str(exc)
        if "rejected" in detail:
            return {"error": "push_rejected", "detail": detail}, 1
        if "authentication" in detail.lower() or "403" in detail:
            return {"error": "auth_failed", "detail": detail}, 1
        return {"error": "push_failed", "detail": detail}, 1

    sha = head_sha(repo) if not args.dry_run else "dry-run"
    return {
        "branch": branch,
        "remote": f"origin/{branch}",
        "commit_sha": sha,
        "tracking_set": not tracking,
        "already_up_to_date": False,
        "dry_run": args.dry_run,
    }, 0


def cmd_publish_to_governance(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    feature_id = args.feature_id
    governance_repo = args.governance_repo
    control_repo = args.control_repo

    err = validate_slug(feature_id, "feature_id")
    if err:
        return {"error": "invalid_feature_id", "detail": err}, 1

    yaml_path = find_feature_yaml(governance_repo, feature_id)
    if yaml_path is None:
        return {"error": "feature_yaml_not_found", "feature_id": feature_id}, 1

    feature_data = load_feature_yaml(yaml_path)
    if not feature_data:
        return {"error": "invalid_feature_yaml", "path": str(yaml_path)}, 1

    resolved_feature_id = feature_identifier(feature_data) or feature_id
    control_docs_root, governance_docs_root = resolve_docs_roots(
        control_repo, governance_repo, feature_data, resolved_feature_id
    )
    control_docs_root = normalize_publish_path(control_docs_root)
    governance_docs_root = normalize_publish_path(governance_docs_root)

    if not control_docs_root.exists():
        return {
            "error": "control_docs_not_found",
            "control_docs_path": str(control_docs_root),
        }, 1

    requested_artifacts = list(args.artifact or PHASE_ARTIFACTS.get(args.phase, []))
    if not requested_artifacts:
        return {"error": "no_artifacts_for_phase", "phase": args.phase}, 1

    published_files: list[str] = []
    missing_artifacts: list[str] = []
    copied_from: list[str] = []
    matched_review_filename: str | None = None

    for artifact_name in requested_artifacts:
        source_files = existing_artifact_files(control_docs_root, artifact_name, phase=args.phase)
        if not source_files:
            missing_artifacts.append(artifact_name)
            continue

        if args.phase == "expressplan" and artifact_name == "review-report":
            # Enforce explicit fallback order and report which filename was matched.
            source_files = [source_files[0]]
            matched_review_filename = source_files[0].name

        for source_path in source_files:
            source_path = normalize_publish_path(source_path)
            destination_path = normalize_publish_path(governance_docs_root / source_path.name)
            copied_from.append(str(source_path))
            published_files.append(str(destination_path))
            if not args.dry_run:
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, destination_path)

    if not published_files:
        return {
            "error": "no_artifacts_published",
            "feature_id": resolved_feature_id,
            "phase": args.phase,
            "control_docs_path": str(control_docs_root),
            "governance_docs_path": str(governance_docs_root),
            "missing_artifacts": missing_artifacts,
            "requested_artifacts": requested_artifacts,
        }, 1

    return {
        "feature_id": resolved_feature_id,
        "phase": args.phase,
        "requested_artifacts": requested_artifacts,
        "control_docs_path": str(control_docs_root),
        "governance_docs_path": str(governance_docs_root),
        "copied_from": copied_from,
        "published_files": published_files,
        "missing_artifacts": missing_artifacts,
        "matched_review_filename": matched_review_filename,
        "express_review_resolution_order": [
            "expressplan-adversarial-review.md",
            "expressplan-review.md",
        ]
        if args.phase == "expressplan"
        else [],
        "dry_run": args.dry_run,
    }, 0


def cmd_validate_phase_start(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Validate topology, base branch, and track before phase writes begin."""
    feature_id = args.feature_id
    repo = args.repo
    governance_repo = args.governance_repo
    expected_base = args.expected_base_branch or feature_id

    missing = missing_control_branches(repo, feature_id)
    if missing:
        return {
            "error": "missing_required_branch",
            "feature_id": feature_id,
            "missing_branches": missing,
            "action": "init-feature",
            "detail": "Required control branches are missing. Re-run init-feature/create-feature-branches.",
        }, 1

    cb = current_branch(repo)
    if cb != expected_base:
        return {
            "error": "base_branch_mismatch",
            "feature_id": feature_id,
            "current_branch": cb,
            "expected_base_branch": expected_base,
            "detail": "Phase start must begin from the intended base branch.",
        }, 1

    yaml_path = find_feature_yaml(governance_repo, feature_id)
    if yaml_path is None:
        return {"error": "feature_yaml_not_found", "feature_id": feature_id}, 1
    feature_data = load_feature_yaml(yaml_path)
    if not feature_data:
        return {"error": "invalid_feature_yaml", "path": str(yaml_path)}, 1
    raw_track = str(feature_data.get("track") or "").strip().lower()
    track = canonical_track(raw_track)
    if track not in SUPPORTED_TRACKS:
        return {
            "error": "constitution_track_not_permitted",
            "feature_id": feature_id,
            "track": raw_track,
            "track_canonical": track,
            "detail": "Track failed phase-start constitution gate.",
        }, 1

    return {
        "status": "pass",
        "feature_id": feature_id,
        "current_branch": cb,
        "expected_base_branch": expected_base,
        "track": raw_track,
        "track_canonical": track,
        "constitution_gate": "pass",
        "required_branches": required_control_branches(feature_id),
        "message": "Phase-start validation passed.",
    }, 0


def cmd_cleanup_branch(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Delete merged step branch, then switch/pull the next branch. Idempotent by design."""
    repo = args.repo
    branch = args.branch
    next_branch = args.next_branch

    dirty = verify_clean(repo)
    if dirty:
        return {"error": "dirty_working_tree", "detail": dirty}, 1

    if not branch_exists(repo, next_branch, include_remote=True):
        return {"error": "next_branch_not_found", "branch": next_branch}, 1

    runner = Runner(args.dry_run, repo)
    current = current_branch(repo)
    local_deleted = False
    remote_deleted = False

    try:
        if current == branch:
            runner.run(["checkout", next_branch])

        if branch_exists(repo, branch):
            runner.run(["branch", "-D", branch])
            local_deleted = True

        if branch_exists(repo, branch, include_remote=True):
            remote_exists = git(["branch", "-r", "--list", f"origin/{branch}"], cwd=repo).stdout.strip()
            if remote_exists:
                runner.run(["push", "origin", "--delete", branch])
                remote_deleted = True

        runner.run(["checkout", next_branch])
        runner.run(["pull", "origin", next_branch])
    except RuntimeError as exc:
        return {"error": "cleanup_failed", "detail": str(exc)}, 1

    return {
        "status": "pass",
        "branch": branch,
        "next_branch": next_branch,
        "local_deleted": local_deleted,
        "remote_deleted": remote_deleted,
        "switched_and_pulled": True,
        "working_tree_clean_verified": True,
        "idempotent": True,
        "dry_run": args.dry_run,
    }, 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Lens git write operations for the 3-branch control feature model"
    )
    sub = p.add_subparsers(dest="command", required=True)

    # create-feature-branches
    cfb = sub.add_parser("create-feature-branches", help="Create {featureId} + {featureId}-plan + {featureId}-dev branches")
    cfb.add_argument("--governance-repo", required=True)
    cfb.add_argument("--feature-id", required=True)
    cfb.add_argument("--repo", default=None, help="Working repo path (defaults to governance-repo)")
    cfb.add_argument("--default-branch", default=None, help="Override the repo default branch")
    cfb.add_argument("--dry-run", action="store_true")

    # commit-artifacts
    ca = sub.add_parser("commit-artifacts", help="Stage and commit files with structured message")
    ca.add_argument("--repo", required=True)
    ca.add_argument("--governance-repo", default=None)
    ca.add_argument("--feature-id", required=True)
    ca.add_argument("--files", nargs="+", required=True)
    ca.add_argument("--description", required=False)
    ca.add_argument("--message", required=False, help="Compatibility alias for --description")
    ca.add_argument("--phase", default=None, help="Phase token; auto-resolved from feature.yaml if omitted")
    ca.add_argument("--phase-step", default=None, help="Optional phase step token for branch routing (for example: step1/step2/step3)")
    ca.add_argument("--push", action="store_true")
    ca.add_argument("--no-confirm", action="store_true")
    ca.add_argument("--dry-run", action="store_true")

    # create-dev-branch
    cdb = sub.add_parser("create-dev-branch", help="Create {featureId}-dev-{username} branch")
    cdb.add_argument("--governance-repo", required=True)
    cdb.add_argument("--feature-id", required=True)
    cdb.add_argument("--username", required=True)
    cdb.add_argument("--repo", default=None)
    cdb.add_argument("--dry-run", action="store_true")

    # prepare-dev-branch
    pdb = sub.add_parser("prepare-dev-branch", help="Prepare the target repo working branch for a dev cycle")
    pdb.add_argument("--repo", required=True)
    pdb.add_argument("--feature-id", required=True)
    pdb.add_argument("--feature-slug", default=None, help="Optional short slug used for target-repo feature/* branch names")
    pdb.add_argument("--mode", required=True, help="Repo-scoped dev mode: direct-default, feature-id, or feature-id-username")
    pdb.add_argument("--username", default=None, help="Required when mode=feature-id-username")
    pdb.add_argument("--base-branch", default=None, help="Override the repo default branch")
    pdb.add_argument("--governance-repo", default=None, help="Governance repo containing repo-inventory.yaml")
    pdb.add_argument("--dry-run", action="store_true")

    # merge-plan
    mp = sub.add_parser("merge-plan", help="Merge {featureId}-plan into {featureId}")
    mp.add_argument("--governance-repo", required=True)
    mp.add_argument("--feature-id", required=True)
    mp.add_argument("--repo", default=None)
    mp.add_argument("--strategy", choices=["pr", "direct"], default="pr")
    mp.add_argument("--auto-merge", action="store_true")
    mp.add_argument("--delete-after-merge", action="store_true")
    mp.add_argument("--dry-run", action="store_true")

    # create-pr
    cp = sub.add_parser("create-pr", help="Create or validate a pull request between two branches")
    cp.add_argument("--governance-repo", required=True)
    cp.add_argument("--repo", default=None)
    cp.add_argument("--base", required=False)
    cp.add_argument("--target-branch", required=False, help="Compatibility alias for --base")
    cp.add_argument("--head", required=False)
    cp.add_argument("--source-branch", required=False, help="Compatibility alias for --head")
    cp.add_argument("--title", default=None)
    cp.add_argument("--body", default="Auto-created by lens-git-orchestration")
    cp.add_argument("--auto-detect-base", action="store_true")
    cp.add_argument("--auto-merge", action="store_true")
    cp.add_argument("--dry-run", action="store_true")

    # push
    pu = sub.add_parser("push", help="Push current or named branch to remote")
    pu.add_argument("--governance-repo", required=True)
    pu.add_argument("--repo", default=None)
    pu.add_argument("--branch", default=None)
    pu.add_argument("--dry-run", action="store_true")

    # publish-to-governance
    ptg = sub.add_parser("publish-to-governance", help="Copy staged planning artifacts into governance docs path")
    ptg.add_argument("--governance-repo", required=True)
    ptg.add_argument("--control-repo", required=True)
    ptg.add_argument("--feature-id", required=True)
    ptg.add_argument("--phase", required=True, choices=sorted(PHASE_ARTIFACTS.keys()))
    ptg.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Specific artifact name to publish (repeatable, defaults to the phase artifact set)",
    )
    ptg.add_argument("--dry-run", action="store_true")

    # validate-phase-start
    vps = sub.add_parser("validate-phase-start", help="Validate control branches/base branch/track before phase writes")
    vps.add_argument("--governance-repo", required=True)
    vps.add_argument("--repo", required=True)
    vps.add_argument("--feature-id", required=True)
    vps.add_argument("--expected-base-branch", default=None)

    # cleanup-branch
    cln = sub.add_parser("cleanup-branch", help="Delete merged branch, switch to next branch, and pull")
    cln.add_argument("--repo", required=True)
    cln.add_argument("--branch", required=True)
    cln.add_argument("--next-branch", required=True)
    cln.add_argument("--dry-run", action="store_true")

    # set-feature-base-branch
    sfbb = sub.add_parser(
        "set-feature-base-branch",
        help="Set feature_base_branch in governance repo-inventory.yaml and commit+push",
    )
    sfbb.add_argument("--governance-repo", required=True)
    sfbb.add_argument("--repo", required=True)
    sfbb.add_argument("--branch", required=True, help="Branch name to set as feature_base_branch")
    sfbb.add_argument("--dry-run", action="store_true")

    return p


def main() -> int:
    version_err = check_git_version()
    if version_err:
        print(json.dumps({"error": "git_version", "detail": version_err}))
        return 1

    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "create-feature-branches": cmd_create_feature_branches,
        "commit-artifacts": cmd_commit_artifacts,
        "create-dev-branch": cmd_create_dev_branch,
        "prepare-dev-branch": cmd_prepare_dev_branch,
        "create-pr": cmd_create_pr,
        "merge-plan": cmd_merge_plan,
        "publish-to-governance": cmd_publish_to_governance,
        "validate-phase-start": cmd_validate_phase_start,
        "cleanup-branch": cmd_cleanup_branch,
        "push": cmd_push,
        "set-feature-base-branch": cmd_set_feature_base_branch,
    }

    fn = dispatch.get(args.command)
    if fn is None:
        print(json.dumps({"error": "unknown_command", "command": args.command}))
        return 1

    try:
        result, exit_code = fn(args)
    except Exception as exc:
        print(json.dumps({"error": "internal_error", "detail": str(exc)}))
        return 1

    print(json.dumps(result, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
