#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Complete operations — feature lifecycle archival for Lens governance.

Subcommands:
  check-preconditions  Validate a feature is ready to be finalized (read-only).
  finalize             Archive the feature atomically (write; requires --confirm or --dry-run).
  archive-status       Report archive state without modifying any file (read-only).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPLETABLE_PHASES = {"dev", "dev-complete"}
TERMINAL_PHASES = {"complete", "abandoned"}
PLANNING_PHASES = {
    "preplan", "businessplan", "techplan", "finalizeplan",
    "expressplan", "expressplan-complete", "finalizeplan-complete",
    "techplan-complete", "businessplan-complete",
}

SAFE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")

# Governance keys that must never appear after finalize that weren't there before
ALLOWED_WRITE_FILES = {"feature.yaml", "feature-index.yaml", "summary.md"}


# ---------------------------------------------------------------------------
# Custom config exceptions
# ---------------------------------------------------------------------------

class _ConfigMissingError(ValueError):
    """Raised when governance repo config is not found in any expected location."""


class _ConfigMalformedError(ValueError):
    """Raised when a config file exists but cannot be parsed."""


# ---------------------------------------------------------------------------
# JSON output helpers
# ---------------------------------------------------------------------------

def _out(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _fail(error: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "fail", "error": error, "message": message, **extra}


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file and return a dict. Raises ValueError on parse/read failure."""
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping, got {type(data).__name__}")
    return data


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write YAML to path atomically via a temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _atomic_write_text(path: Path, content: str) -> None:
    """Write text to path atomically via a temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Governance path resolution
# ---------------------------------------------------------------------------

def _resolve_governance_repo(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "governance_repo", None)
    if explicit:
        return Path(explicit).resolve()

    workspace_root = Path(getattr(args, "workspace_root", None) or os.getcwd()).resolve()
    override = workspace_root / ".lens" / "governance-setup.yaml"
    if override.exists():
        try:
            data = _read_yaml(override)
        except ValueError as exc:
            raise _ConfigMalformedError(f"Could not parse {override}: {exc}") from exc
        val = str(data.get("governance_repo_path") or "").strip()
        if val:
            return Path(val.replace("{project-root}", str(workspace_root))).resolve()

    for candidate in [
        workspace_root / "_bmad" / "lens-work" / "bmadconfig.yaml",
        workspace_root / "lens.core" / "_bmad" / "lens-work" / "bmadconfig.yaml",
    ]:
        if candidate.exists():
            try:
                data = _read_yaml(candidate)
            except ValueError as exc:
                raise _ConfigMalformedError(f"Could not parse {candidate}: {exc}") from exc
            val = str(data.get("governance_repo_path") or "").strip()
            if val:
                return Path(val.replace("{project-root}", str(workspace_root))).resolve()

    raise _ConfigMissingError("governance_repo_path not found in any config. Run /lens-onboard first.")


def _discover_feature_dir(governance_repo: Path, feature_id: str) -> Path | None:
    """Find the feature directory by scanning features/{domain}/{service}/{featureId}/.

    Returns None if feature_id is invalid, the features root does not exist,
    or no matching directory is found.
    """
    if not SAFE_ID_PATTERN.match(feature_id):
        return None
    features_root = governance_repo / "features"
    if not features_root.is_dir():
        return None
    for feature_yaml in features_root.rglob("feature.yaml"):
        if feature_yaml.parent.name == feature_id:
            return feature_yaml.parent
    return None


def _find_feature_yaml(governance_repo: Path, feature_id: str) -> tuple[Path | None, str | None]:
    """Return (path to feature.yaml, None) or (None, error_code) if not found or ID invalid."""
    if not SAFE_ID_PATTERN.match(feature_id):
        return None, "feature_id_invalid"
    feature_dir = _discover_feature_dir(governance_repo, feature_id)
    if feature_dir:
        return feature_dir / "feature.yaml", None
    return None, "feature_not_found"


# ---------------------------------------------------------------------------
# Retrospective check helpers
# ---------------------------------------------------------------------------

def _check_retrospective(feature_dir: Path) -> dict[str, Any] | None:
    """Return a blocker dict if retrospective is missing or not approved, else None."""
    retro_path = feature_dir / "retrospective.md"
    if not retro_path.exists():
        return {
            "name": "retrospective",
            "status": "fail",
            "blocker": "retrospective_missing",
            "message": (
                "retrospective.md is required before completing a feature. "
                "Run 'lens-retrospective' to create it, then set status: approved."
            ),
        }

    text = retro_path.read_text(encoding="utf-8")

    if not text.startswith("---"):
        return {
            "name": "retrospective",
            "status": "fail",
            "blocker": "retrospective_not_approved",
            "retrospective_status": "no_frontmatter",
            "message": (
                "retrospective.md has no YAML frontmatter. "
                "Add frontmatter with status: approved before completing."
            ),
        }

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {
            "name": "retrospective",
            "status": "fail",
            "blocker": "retrospective_not_approved",
            "retrospective_status": "malformed_frontmatter",
            "message": (
                "retrospective.md has an unterminated frontmatter block. "
                "Fix the YAML and set status: approved before completing."
            ),
        }

    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {
            "name": "retrospective",
            "status": "fail",
            "blocker": "retrospective_not_approved",
            "retrospective_status": "malformed_frontmatter",
            "message": (
                "retrospective.md frontmatter could not be parsed. "
                "Fix the YAML and set status: approved before completing."
            ),
        }

    if not isinstance(fm, dict):
        return {
            "name": "retrospective",
            "status": "fail",
            "blocker": "retrospective_not_approved",
            "retrospective_status": "malformed_frontmatter",
            "message": (
                "retrospective.md frontmatter is not a YAML mapping. "
                "Fix the YAML and set status: approved before completing."
            ),
        }

    retro_status = str(fm.get("status") or "").strip()
    if retro_status != "approved":
        return {
            "name": "retrospective",
            "status": "fail",
            "blocker": "retrospective_not_approved",
            "retrospective_status": retro_status,
            "message": (
                f"retrospective.md exists but status is '{retro_status}', not 'approved'. "
                "Update the file and set status: approved before completing."
            ),
        }

    return None


def _check_document_project(feature_dir: Path) -> dict[str, Any]:
    """Check for document-project output (advisory, not a blocker)."""
    # Common document-project output patterns
    indicators = [
        feature_dir / "project-documentation.md",
        feature_dir / "project-docs.md",
        feature_dir / "docs" / "project-documentation.md",
    ]
    found = any(p.exists() for p in indicators)
    if found:
        return {"name": "document_project", "status": "pass", "message": "Project documentation artifact found."}
    return {
        "name": "document_project",
        "status": "warn",
        "message": (
            "No project documentation artifact found. "
            "Consider running lens-document-project before finalizing."
        ),
    }


# ---------------------------------------------------------------------------
# Control repo merge helper
# ---------------------------------------------------------------------------

def _gh_merge_to_main(
    control_repo: Path,
    feature_id: str,
    dry_run: bool,
    head_branch: str | None = None,
    base_branch: str = "main",
) -> tuple[str | None, str | None]:
    """Validate, merge, and clean up normal control-repo completion branches.

    Returns (pr_url, None) on success, or (None, error_msg) on failure.
    On dry_run, returns ('dry_run', None) without executing any commands.
    """
    if dry_run:
        return "dry_run", None

    head_branch = head_branch or f"{feature_id}-dev"
    feature_branch = feature_id
    plan_branch = f"{feature_id}-plan"
    cleanup_branches = [plan_branch, feature_branch, head_branch]
    cwd = str(control_repo)

    def _git(*cmd_args: str) -> tuple[int, str, str]:
        try:
            r = subprocess.run(
                ["git", *cmd_args], cwd=cwd, capture_output=True, text=True, timeout=60
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except FileNotFoundError:
            return -1, "", "git CLI not found."
        except subprocess.TimeoutExpired:
            return -1, "", "git command timed out after 60 s."

    def _gh(*cmd_args: str) -> tuple[int, str, str]:
        try:
            r = subprocess.run(
                ["gh", *cmd_args], cwd=cwd, capture_output=True, text=True, timeout=60
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except FileNotFoundError:
            return -1, "", "gh CLI not found. Install GitHub CLI (https://cli.github.com/)."
        except subprocess.TimeoutExpired:
            return -1, "", "gh command timed out after 60 s."

    code, out, err = _git("status", "--porcelain")
    if code != 0:
        return None, f"control repo status failed: {err or out}"
    if out:
        return None, f"control repo has uncommitted changes; commit them on {head_branch} before finalizing."

    def _branch_ref(branch: str, required: bool = True) -> tuple[str | None, str | None]:
        code, out, err = _git("rev-parse", "--verify", branch)
        if code == 0:
            return branch, None
        code, out, err = _git("rev-parse", "--verify", f"origin/{branch}")
        if code == 0:
            return f"origin/{branch}", None
        if required:
            return None, f"required control branch '{branch}' was not found locally or on origin."
        return None, None

    def _is_ancestor(ancestor_ref: str, descendant_ref: str) -> tuple[bool, str | None]:
        code, out, err = _git("merge-base", "--is-ancestor", ancestor_ref, descendant_ref)
        if code == 0:
            return True, None
        if code == 1:
            return False, None
        return False, err or out or f"git merge-base failed for {ancestor_ref} -> {descendant_ref}."

    def _validate_merged(ancestor_branch: str, ancestor_ref: str, descendant_branch: str, descendant_ref: str) -> str | None:
        merged, merge_error = _is_ancestor(ancestor_ref, descendant_ref)
        if merge_error:
            return merge_error
        if not merged:
            return (
                f"control branch validation failed: '{ancestor_branch}' is not merged into "
                f"'{descendant_branch}'. Merge related control branches before completing."
            )
        return None

    code, out, err = _git("fetch", "--prune", "origin")
    if code != 0:
        return None, f"control repo fetch failed: {err or out}"

    base_ref, ref_error = _branch_ref(f"origin/{base_branch}")
    if ref_error:
        return None, ref_error
    head_ref, ref_error = _branch_ref(head_branch)
    if ref_error:
        return None, ref_error
    feature_ref, ref_error = _branch_ref(feature_branch)
    if ref_error:
        return None, ref_error
    plan_ref, ref_error = _branch_ref(plan_branch, required=False)
    if ref_error:
        return None, ref_error

    if plan_ref and feature_ref:
        validation_error = _validate_merged(plan_branch, plan_ref, feature_branch, feature_ref)
        if validation_error:
            return None, validation_error
    if feature_ref and head_ref:
        validation_error = _validate_merged(feature_branch, feature_ref, head_branch, head_ref)
        if validation_error:
            return None, validation_error

    code, out, err = _git("rev-parse", "--verify", head_branch)
    if code == 0:
        code, out, err = _git("checkout", head_branch)
        if code != 0:
            return None, f"control repo checkout {head_branch} failed: {err or out}"
    else:
        start_point = head_ref or f"origin/{base_branch}"
        code, out, err = _git("checkout", "-B", head_branch, start_point)
        if code != 0:
            return None, f"control repo checkout {head_branch} failed: {err or out}"

    code, out, err = _git("rev-parse", "--verify", f"origin/{head_branch}")
    if code == 0:
        code, out, err = _git("pull", "--ff-only", "origin", head_branch)
        if code != 0:
            return None, f"control repo pull {head_branch} failed: {err or out}"

    code, out, err = _git("push", "-u", "origin", head_branch)
    if code != 0:
        return None, f"control repo push {head_branch} failed: {err or out}"

    # Check for an existing open or merged PR to avoid duplicates
    code, out, err = _gh(
        "pr", "list",
        "--head", head_branch,
        "--base", base_branch,
        "--json", "url,state",
        "--limit", "1",
        "--state", "all",
    )
    if code != 0:
        return None, f"PR lookup failed: {err or out}"

    pr_url: str | None = None
    already_merged = False
    try:
        prs = json.loads(out or "[]")
    except json.JSONDecodeError:
        prs = []

    if prs:
        existing = prs[0]
        state = str(existing.get("state") or "").upper()
        if state == "MERGED":
            pr_url = existing.get("url", "already_merged")
            already_merged = True
        else:
            pr_url = existing.get("url", "")

    if not pr_url:
        code, out, err = _gh(
            "pr", "create",
            "--head", head_branch,
            "--base", base_branch,
            "--title", f"[complete] {feature_id} — docs delivery to main",
            "--body",
            (
                f"Final merge of planning docs and dev artifacts for {feature_id}.\n\n"
                "Feature status: **complete** (archived in governance)."
            ),
        )
        if code != 0:
            return None, f"gh pr create failed: {err or out}"
        pr_url = out

    if not already_merged:
        code, out, err = _gh("pr", "merge", pr_url, "--merge")
        if code != 0:
            return pr_url, f"PR created at {pr_url} but merge failed: {err or out}"

    code, out, err = _git("fetch", "--prune", "origin")
    if code != 0:
        return pr_url, f"PR merged at {pr_url} but post-merge fetch failed: {err or out}"

    base_ref, ref_error = _branch_ref(base_branch)
    if ref_error:
        return pr_url, f"PR merged at {pr_url} but {ref_error}"
    head_ref, _ = _branch_ref(head_branch, required=False)
    if head_ref:
        validation_error = _validate_merged(head_branch, head_ref, base_branch, base_ref or base_branch)
        if validation_error:
            return pr_url, f"PR merged at {pr_url} but {validation_error}"

    code, out, err = _git("checkout", base_branch)
    if code != 0:
        return pr_url, f"PR merged at {pr_url} but checkout {base_branch} failed: {err or out}"
    code, out, err = _git("pull", "--ff-only", "origin", base_branch)
    if code != 0:
        return pr_url, f"PR merged at {pr_url} but pull {base_branch} failed: {err or out}"

    cleanup_errors: list[str] = []
    for branch in cleanup_branches:
        local_ref, _ = _branch_ref(branch, required=False)
        if local_ref == branch:
            code, out, err = _git("branch", "-d", branch)
            if code != 0:
                cleanup_errors.append(f"delete local {branch}: {err or out}")
        remote_ref, _ = _branch_ref(f"origin/{branch}", required=False)
        if remote_ref:
            code, out, err = _git("push", "origin", "--delete", branch)
            if code != 0:
                cleanup_errors.append(f"delete remote {branch}: {err or out}")

    code, out, err = _git("fetch", "--prune", "origin")
    if code != 0:
        cleanup_errors.append(f"final prune: {err or out}")

    if cleanup_errors:
        return pr_url, f"PR merged at {pr_url}, but branch cleanup failed: {'; '.join(cleanup_errors)}"

    return pr_url, None


# ---------------------------------------------------------------------------
# check-preconditions
# ---------------------------------------------------------------------------

def cmd_check_preconditions(args: argparse.Namespace) -> int:
    feature_id = str(getattr(args, "feature_id", "") or "").strip()
    if not feature_id:
        _out(_fail("feature_id_missing", "Provide --feature-id."))
        return 1

    try:
        governance_repo = _resolve_governance_repo(args)
    except _ConfigMalformedError as exc:
        _out(_fail("config_malformed", str(exc)))
        return 1
    except ValueError as exc:
        _out(_fail("config_missing", str(exc)))
        return 1

    feature_yaml_path, lookup_error = _find_feature_yaml(governance_repo, feature_id)
    if feature_yaml_path is None:
        if lookup_error == "feature_id_invalid":
            _out(_fail("feature_id_invalid", f"Feature ID '{feature_id}' contains invalid characters. Use lowercase alphanumeric, hyphens, underscores, or dots."))
        else:
            _out(_fail("feature_not_found", f"feature.yaml not found for '{feature_id}' in {governance_repo}/features/."))
        return 1

    try:
        feature_data = _read_yaml(feature_yaml_path)
    except ValueError as exc:
        _out(_fail("feature_yaml_malformed", str(exc)))
        return 1

    feature_dir = feature_yaml_path.parent
    phase = str(feature_data.get("phase") or "").strip()
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    # Phase check
    if phase in TERMINAL_PHASES:
        phase_check = {
            "name": "phase",
            "status": "fail",
            "blocker": "already_terminal",
            "message": f"Feature phase is '{phase}'; feature is already terminal and cannot be re-completed.",
        }
        blockers.append("already_terminal")
    elif phase in PLANNING_PHASES:
        phase_check = {
            "name": "phase",
            "status": "fail",
            "blocker": "wrong_phase",
            "message": (
                f"Feature phase is '{phase}'; expected dev or dev-complete to complete. "
                "Advance through all planning phases first."
            ),
        }
        blockers.append("wrong_phase")
    elif phase in COMPLETABLE_PHASES:
        phase_check = {"name": "phase", "status": "pass", "message": f"Feature phase '{phase}' is completable."}
    else:
        phase_check = {
            "name": "phase",
            "status": "fail",
            "blocker": "phase_unrecognized",
            "message": f"Feature phase '{phase}' is unrecognized. Expected dev or dev-complete.",
        }
        blockers.append("phase_unrecognized")
    checks.append(phase_check)

    # Retrospective check (blocking)
    retro_result = _check_retrospective(feature_dir)
    if retro_result is not None:
        checks.append(retro_result)
        blockers.append(retro_result["blocker"])
    else:
        checks.append({"name": "retrospective", "status": "pass", "message": "retrospective.md exists and status is approved."})

    # Document-project check (advisory)
    doc_check = _check_document_project(feature_dir)
    checks.append(doc_check)
    if doc_check["status"] == "warn":
        warnings.append("document_project_skipped")

    # Aggregate result
    if blockers:
        # Surface the first blocker's message as top-level for easy reading
        first_blocker_check = next(c for c in checks if c.get("status") == "fail")
        _out(
            _fail(
                first_blocker_check.get("blocker", "check_failed"),
                first_blocker_check["message"],
                feature_id=feature_id,
                phase=phase,
                checks=checks,
                blockers=blockers,
                warnings=warnings,
            )
        )
        return 1

    overall = "warn" if warnings else "pass"
    _out(
        {
            "status": overall,
            "feature_id": feature_id,
            "phase": phase,
            "retrospective_skipped": False,
            "document_project_skipped": bool(warnings),
            "checks": checks,
            "warnings": warnings,
            "blockers": [],
        }
    )
    return 0


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------

def cmd_finalize(args: argparse.Namespace) -> int:
    feature_id = str(getattr(args, "feature_id", "") or "").strip()
    dry_run: bool = bool(getattr(args, "dry_run", False))
    confirm: bool = bool(getattr(args, "confirm", False))
    control_repo_str: str | None = getattr(args, "control_repo", None) or None
    control_repo: Path | None = Path(control_repo_str).resolve() if control_repo_str else None

    if not feature_id:
        _out(_fail("feature_id_missing", "Provide --feature-id."))
        return 1

    if not dry_run and not confirm:
        _out(
            _fail(
                "confirmation_required",
                "finalize is irreversible. Pass --confirm to execute or --dry-run to preview.",
            )
        )
        return 1

    try:
        governance_repo = _resolve_governance_repo(args)
    except _ConfigMalformedError as exc:
        _out(_fail("config_malformed", str(exc)))
        return 1
    except ValueError as exc:
        _out(_fail("config_missing", str(exc)))
        return 1

    feature_yaml_path, lookup_error = _find_feature_yaml(governance_repo, feature_id)
    if feature_yaml_path is None:
        if lookup_error == "feature_id_invalid":
            _out(_fail("feature_id_invalid", f"Feature ID '{feature_id}' contains invalid characters. Use lowercase alphanumeric, hyphens, underscores, or dots."))
        else:
            _out(_fail("feature_not_found", f"feature.yaml not found for '{feature_id}'."))
        return 1

    try:
        feature_data = _read_yaml(feature_yaml_path)
    except ValueError as exc:
        _out(_fail("feature_yaml_malformed", str(exc)))
        return 1

    # Run preconditions — finalize requires pass or warn; fail aborts
    phase = str(feature_data.get("phase") or "").strip()
    feature_dir = feature_yaml_path.parent

    # Inline precondition check for finalize (mirrors check-preconditions logic)
    retro_result = _check_retrospective(feature_dir)
    if phase not in COMPLETABLE_PHASES:
        _out(
            _fail(
                "wrong_phase",
                f"Feature phase is '{phase}'; expected dev or dev-complete. check-preconditions failed.",
                feature_id=feature_id,
                phase=phase,
            )
        )
        return 1
    if retro_result is not None:
        _out(
            _fail(
                retro_result["blocker"],
                retro_result["message"],
                feature_id=feature_id,
            )
        )
        return 1

    # Load feature-index.yaml
    index_path = governance_repo / "feature-index.yaml"
    if not index_path.exists():
        _out(_fail("feature_index_malformed", f"feature-index.yaml not found at {index_path}."))
        return 1
    try:
        index_data = _read_yaml(index_path)
    except ValueError as exc:
        _out(_fail("feature_index_malformed", str(exc)))
        return 1

    # Validate feature-index.yaml structure: must have a features list with the entry
    entries = index_data.get("features")
    if not isinstance(entries, list):
        _out(_fail("index_malformed", "feature-index.yaml 'features' key is not a list or is missing."))
        return 1
    feature_index_entry = next(
        (e for e in entries if isinstance(e, dict) and (e.get("id") == feature_id or e.get("featureId") == feature_id)),
        None,
    )
    if feature_index_entry is None:
        _out(_fail("feature_not_indexed", f"Feature '{feature_id}' not found in feature-index.yaml features list."))
        return 1

    summary_path = feature_dir / "summary.md"
    now_ts = datetime.now(timezone.utc).isoformat()

    planned_changes = [
        {"path": str(feature_yaml_path.relative_to(governance_repo)), "change": f"phase: {phase} → complete, completed_at: {now_ts}"},
        {"path": str(index_path.relative_to(governance_repo)), "change": f"status for '{feature_id}': {feature_index_entry.get('status', 'unknown')} → archived"},
        {"path": str(summary_path.relative_to(governance_repo)), "change": "write archive summary section"},
    ]
    if control_repo is not None:
        planned_changes.append({
            "repo": str(control_repo),
            "change": f"validate branches and merge PR: {feature_id}-dev -> main; delete related branches",
        })

    doc_check = _check_document_project(feature_dir)
    warnings = []
    if doc_check["status"] == "warn":
        warnings.append("document_project_skipped")

    if dry_run:
        _out(
            {
                "status": "dry_run",
                "feature_id": feature_id,
                "planned_changes": planned_changes,
                "warnings": warnings,
            }
        )
        return 0

    # Capture original content before any writes to enable rollback
    original_feature_text = feature_yaml_path.read_text(encoding="utf-8")
    original_index_text = index_path.read_text(encoding="utf-8")

    # --- Execute atomic writes ---
    # 1. Update feature.yaml
    feature_data["phase"] = "complete"
    feature_data["completed_at"] = now_ts
    # Record the transition
    transitions = feature_data.get("phase_transitions")
    if not isinstance(transitions, list):
        transitions = []
    transitions.append({"phase": "complete", "timestamp": now_ts, "user": "lens-complete"})
    feature_data["phase_transitions"] = transitions

    try:
        _atomic_write_yaml(feature_yaml_path, feature_data)
    except Exception as exc:
        _out(_fail("write_failed", f"Failed to write feature.yaml: {exc}"))
        return 1

    # 2. Update feature-index.yaml
    feature_index_entry["status"] = "archived"
    feature_index_entry["updated_at"] = now_ts

    try:
        _atomic_write_yaml(index_path, index_data)
    except Exception as exc:
        # Rollback feature.yaml to its original content
        rollback_note = ""
        try:
            _atomic_write_text(feature_yaml_path, original_feature_text)
            rollback_note = " Rolled back feature.yaml."
        except Exception as rb_exc:
            rollback_note = f" feature.yaml rollback also failed ({rb_exc}); manual intervention required."
        _out(_fail("write_failed", f"Failed to write feature-index.yaml: {exc}.{rollback_note}"))
        return 1

    # 3. Write summary.md
    summary_content = _build_summary(feature_data, feature_id, now_ts)
    try:
        _atomic_write_text(summary_path, summary_content)
    except Exception as exc:
        # Rollback both feature.yaml and feature-index.yaml
        rollback_notes = []
        try:
            _atomic_write_text(feature_yaml_path, original_feature_text)
            rollback_notes.append("feature.yaml rolled back")
        except Exception as rb_exc:
            rollback_notes.append(f"feature.yaml rollback failed ({rb_exc})")
        try:
            _atomic_write_text(index_path, original_index_text)
            rollback_notes.append("feature-index.yaml rolled back")
        except Exception as rb_exc:
            rollback_notes.append(f"feature-index.yaml rollback failed ({rb_exc})")
        rollback_summary = "; ".join(rollback_notes)
        _out(_fail("write_failed", f"Failed to write summary.md: {exc}. {rollback_summary}. Manual intervention may be required."))
        return 1

    changes_applied = [
        {"path": str(feature_yaml_path.relative_to(governance_repo)), "change": "phase → complete"},
        {"path": str(index_path.relative_to(governance_repo)), "change": "status → archived"},
        {"path": str(summary_path.relative_to(governance_repo)), "change": "archive summary written"},
    ]

    # Merge {featureId}-dev -> main in the control repo if requested
    merge_pr_url: str | None = None
    merge_warning: str | None = None
    if control_repo is not None:
        merge_pr_url, merge_error = _gh_merge_to_main(control_repo, feature_id, dry_run=False)
        if merge_error:
            # Non-fatal: governance writes succeeded; surface as warning
            merge_warning = merge_error
            warnings.append(f"control_repo_merge_failed: {merge_error}")
        else:
            changes_applied.append({
                "repo": str(control_repo),
                "change": f"PR merged and related branches deleted: {feature_id}-dev -> main",
                "pr_url": merge_pr_url or "",
            })

    _out(
        {
            "status": "complete",
            "feature_id": feature_id,
            "archived_at": now_ts,
            "changes_applied": changes_applied,
            "retrospective_skipped": False,
            "document_project_skipped": bool(doc_check["status"] == "warn"),
            "warnings": warnings,
        }
    )
    return 0


def _index_status(index_data: dict[str, Any], feature_id: str) -> str:
    for entry in index_data.get("features") or []:
        if isinstance(entry, dict) and (entry.get("id") == feature_id or entry.get("featureId") == feature_id):
            return str(entry.get("status") or "unknown")
    return "not_found"


def _build_summary(feature_data: dict[str, Any], feature_id: str, archived_at: str) -> str:
    name = feature_data.get("name") or feature_id
    domain = feature_data.get("domain") or ""
    service = feature_data.get("service") or ""
    track = feature_data.get("track") or ""
    return (
        f"---\n"
        f"feature: {feature_id}\n"
        f"doc_type: summary\n"
        f"status: archived\n"
        f"archived_at: {archived_at}\n"
        f"---\n\n"
        f"# {name}\n\n"
        f"**Domain:** {domain}  \n"
        f"**Service:** {service}  \n"
        f"**Track:** {track}  \n"
        f"**Archived:** {archived_at}\n\n"
        f"## Archive Notes\n\n"
        f"Feature archived via `lens-complete`. "
        f"See `feature.yaml` for full lifecycle history.\n"
    )


# ---------------------------------------------------------------------------
# archive-status
# ---------------------------------------------------------------------------

def cmd_archive_status(args: argparse.Namespace) -> int:
    feature_id = str(getattr(args, "feature_id", "") or "").strip()
    if not feature_id:
        _out(_fail("feature_id_missing", "Provide --feature-id."))
        return 1

    try:
        governance_repo = _resolve_governance_repo(args)
    except _ConfigMalformedError as exc:
        _out(_fail("config_malformed", str(exc)))
        return 1
    except ValueError as exc:
        _out(_fail("config_missing", str(exc)))
        return 1

    feature_yaml_path, lookup_error = _find_feature_yaml(governance_repo, feature_id)
    if feature_yaml_path is None:
        if lookup_error == "feature_id_invalid":
            _out(_fail("feature_id_invalid", f"Feature ID '{feature_id}' contains invalid characters. Use lowercase alphanumeric, hyphens, underscores, or dots."))
        else:
            _out(_fail("feature_not_found", f"feature.yaml not found for '{feature_id}'."))
        return 1

    try:
        feature_data = _read_yaml(feature_yaml_path)
    except ValueError as exc:
        _out(_fail("feature_yaml_malformed", str(exc)))
        return 1

    index_path = governance_repo / "feature-index.yaml"
    index_status = "unknown"
    if index_path.exists():
        try:
            index_data = _read_yaml(index_path)
            index_status = _index_status(index_data, feature_id)
        except ValueError:
            index_status = "malformed"

    phase = str(feature_data.get("phase") or "").strip()
    archived = phase in TERMINAL_PHASES
    completed_at = feature_data.get("completed_at")

    _out(
        {
            "status": "pass",
            "feature_id": feature_id,
            "archived": archived,
            "phase": phase,
            "index_status": index_status,
            "completed_at": completed_at,
        }
    )
    return 0


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="complete-ops — Lens feature lifecycle archival operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # Shared parent
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--governance-repo", dest="governance_repo", default=None)
    shared.add_argument("--feature-id", dest="feature_id", required=True)
    shared.add_argument("--workspace-root", dest="workspace_root", default=None)

    # check-preconditions
    sub.add_parser("check-preconditions", parents=[shared],
                   help="Validate a feature is ready to be finalized (read-only)")

    # finalize
    p_fin = sub.add_parser("finalize", parents=[shared],
                            help="Archive a feature atomically")
    p_fin.add_argument("--dry-run", dest="dry_run", action="store_true",
                       help="Preview changes without writing")
    p_fin.add_argument("--confirm", dest="confirm", action="store_true",
                       help="Required for non-dry-run execution")
    p_fin.add_argument("--control-repo", dest="control_repo", default=None,
                       help="Path to the control repo. When provided, creates and merges a PR "
                           "from {featureId}-dev -> main after governance archival, then deletes related branches.")

    # archive-status
    sub.add_parser("archive-status", parents=[shared],
                   help="Report archive state without modifying any file (read-only)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "check-preconditions": cmd_check_preconditions,
        "finalize": cmd_finalize,
        "archive-status": cmd_archive_status,
    }
    handler = dispatch.get(args.subcommand)
    if handler is None:
        _out(_fail("unknown_subcommand", f"Unknown subcommand: {args.subcommand}"))
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
