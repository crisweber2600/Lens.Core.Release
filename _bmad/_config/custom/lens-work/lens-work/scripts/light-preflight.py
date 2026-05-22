#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Lightweight prompt-start git sync for the control and governance repos."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType


AUTO_COMMIT_TEMPLATE = "chore(lens): auto-commit {repo_name} before light preflight sync"
INTERRUPTED_STATE_MARKERS: tuple[tuple[str, str], ...] = (
    ("MERGE_HEAD", "merge in progress"),
    ("CHERRY_PICK_HEAD", "cherry-pick in progress"),
    ("REVERT_HEAD", "revert in progress"),
    ("BISECT_LOG", "bisect in progress"),
    ("rebase-merge", "rebase in progress"),
    ("rebase-apply", "rebase in progress"),
)


def load_preflight_helpers() -> ModuleType:
    script_path = Path(__file__).with_name("preflight.py")
    spec = importlib.util.spec_from_file_location("lens_preflight_helpers", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load preflight helpers from {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HELPERS = load_preflight_helpers()


def git_repo(repo: Path, args: list[str]):
    return HELPERS.git_repo(repo, args)


def git_error(result) -> str:
    return HELPERS.git_error(result)


def git_symbolic_branch(repo: Path) -> tuple[str | None, str | None]:
    result = git_repo(repo, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    if result.returncode != 0:
        return None, "detached HEAD; check out a branch before light preflight"

    branch = result.stdout.strip()
    if not branch:
        return None, "unable to determine current branch"

    return branch, None


def git_remotes(repo: Path) -> tuple[list[str], str | None]:
    result = git_repo(repo, ["remote"])
    if result.returncode != 0:
        return [], git_error(result)

    remotes = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not remotes:
        return [], "no git remotes configured"

    return remotes, None


def git_upstream(repo: Path) -> tuple[str, str] | None:
    result = git_repo(repo, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    if result.returncode != 0:
        return None

    upstream = result.stdout.strip()
    if not upstream or "/" not in upstream:
        return None

    remote, branch = upstream.split("/", 1)
    if not remote or not branch:
        return None

    return remote, branch


def git_path_exists(repo: Path, marker: str) -> bool:
    result = git_repo(repo, ["rev-parse", "--git-path", marker])
    if result.returncode != 0:
        return False

    candidate = Path(result.stdout.strip())
    if not candidate.is_absolute():
        candidate = repo / candidate

    return candidate.exists()


def detect_interrupted_state(repo: Path) -> str | None:
    for marker, detail in INTERRUPTED_STATE_MARKERS:
        if git_path_exists(repo, marker):
            return detail
    return None


def remote_branch_exists(repo: Path, remote: str, branch: str) -> tuple[bool, str | None]:
    result = git_repo(repo, ["ls-remote", "--exit-code", "--heads", remote, branch])
    if result.returncode == 0:
        return True, None
    if result.returncode == 2:
        return False, None
    return False, git_error(result)


def remote_has_new_commits(
    repo: Path,
    preferred_remote: str | None = None,
    preferred_branch: str | None = None,
) -> tuple[bool, str | None]:
    """Return (has_new, detail). has_new=True means the tracked remote has commits
    the local branch does not contain. Fails open (returns False) on any probe
    error so offline/unreachable remotes do not invalidate a fresh cache.
    """

    if not repo.is_dir():
        return False, "missing directory"

    worktree_check = git_repo(repo, ["rev-parse", "--is-inside-work-tree"])
    if worktree_check.returncode != 0 or worktree_check.stdout.strip() != "true":
        return False, "not a git worktree"

    if preferred_branch is None:
        branch, branch_error = git_symbolic_branch(repo)
        if branch_error or branch is None:
            return False, branch_error or "no branch"
    else:
        branch = preferred_branch

    remote, local_branch, remote_branch_or_error = resolve_sync_target(repo, branch, preferred_remote)
    if remote is None or local_branch is None:
        return False, remote_branch_or_error or "no remote"

    remote_branch = remote_branch_or_error
    ls = git_repo(repo, ["ls-remote", remote, f"refs/heads/{remote_branch}"])
    if ls.returncode != 0:
        return False, f"ls-remote failed: {git_error(ls)}"

    parts = ls.stdout.strip().split()
    if not parts:
        return False, "remote branch absent"

    remote_sha = parts[0]
    local = git_repo(repo, ["rev-parse", local_branch])
    if local.returncode != 0:
        return False, f"rev-parse failed: {git_error(local)}"

    local_sha = local.stdout.strip()
    if remote_sha == local_sha:
        return False, None

    # If the remote SHA is reachable as an ancestor of the local branch tip,
    # the local branch already contains every remote commit (local is ahead).
    # Otherwise the remote has commits the local branch does not include.
    ancestor = git_repo(repo, ["merge-base", "--is-ancestor", remote_sha, local_branch])
    if ancestor.returncode == 0:
        return False, None

    return True, f"remote {remote}/{remote_branch} at {remote_sha[:7]} not in local"


def resolve_sync_target(repo: Path, branch: str, preferred_remote: str | None = None) -> tuple[str, str, str] | tuple[None, None, str]:
    upstream = git_upstream(repo)
    if upstream is not None:
        upstream_remote, upstream_branch = upstream
        if preferred_remote is None or preferred_remote == upstream_remote:
            return upstream_remote, branch, upstream_branch

    remotes, remote_error = git_remotes(repo)
    if remote_error:
        return None, None, remote_error

    remote = preferred_remote if preferred_remote in remotes else ("origin" if "origin" in remotes else remotes[0])
    return remote, branch, branch


def auto_commit_repo(repo: Path, repo_name: str) -> tuple[bool, str]:
    add_result = git_repo(repo, ["add", "-A"])
    if add_result.returncode != 0:
        return False, f"git add failed: {git_error(add_result)}"

    commit_message = AUTO_COMMIT_TEMPLATE.format(repo_name=repo_name)
    commit_result = git_repo(repo, ["commit", "-m", commit_message])
    if commit_result.returncode != 0:
        return False, f"git commit failed: {git_error(commit_result)}"

    return True, commit_message


def sync_repo(
    repo: Path,
    repo_name: str,
    *,
    preferred_branch: str | None = None,
    preferred_remote: str | None = None,
    allow_missing: bool = False,
) -> tuple[bool, dict[str, object]]:
    result: dict[str, object] = {
        "name": repo_name,
        "path": str(repo),
        "status": "pending",
        "branch": None,
        "remote": None,
        "remote_branch": None,
        "committed": False,
        "pulled": False,
        "pushed": False,
        "detail": "",
    }

    if not repo.is_dir():
        detail = f"missing directory: {repo}"
        result["status"] = "skipped" if allow_missing else "failed"
        result["detail"] = detail
        return allow_missing, result

    worktree_check = git_repo(repo, ["rev-parse", "--is-inside-work-tree"])
    if worktree_check.returncode != 0 or worktree_check.stdout.strip() != "true":
        result["status"] = "failed"
        result["detail"] = f"not a git worktree ({git_error(worktree_check)})"
        return False, result

    interrupted = detect_interrupted_state(repo)
    if interrupted is not None:
        result["status"] = "failed"
        result["detail"] = interrupted
        return False, result

    if preferred_branch is None:
        branch, branch_error = git_symbolic_branch(repo)
        if branch_error:
            result["status"] = "failed"
            result["detail"] = branch_error
            return False, result
    else:
        branch = preferred_branch
        checked_out, checkout_detail = HELPERS.ensure_local_branch(repo, branch)
        if not checked_out:
            result["status"] = "failed"
            result["detail"] = f"failed to checkout {branch}: {checkout_detail}"
            return False, result

    remote, local_branch, remote_branch_or_error = resolve_sync_target(repo, branch, preferred_remote)
    if remote is None or local_branch is None:
        result["status"] = "failed"
        result["detail"] = remote_branch_or_error
        return False, result

    remote_branch = remote_branch_or_error
    result["branch"] = local_branch
    result["remote"] = remote
    result["remote_branch"] = remote_branch

    clean, clean_detail = HELPERS.git_has_clean_worktree(repo)
    if not clean:
        if clean_detail != "local changes present":
            result["status"] = "failed"
            result["detail"] = clean_detail or "unable to inspect worktree"
            return False, result

        committed, commit_detail = auto_commit_repo(repo, repo_name)
        if not committed:
            result["status"] = "failed"
            result["detail"] = commit_detail
            return False, result

        result["committed"] = True

    has_remote_branch, remote_branch_error = remote_branch_exists(repo, remote, remote_branch)
    if remote_branch_error is not None:
        result["status"] = "failed"
        result["detail"] = remote_branch_error
        return False, result

    details: list[str] = []
    if result["committed"]:
        details.append("committed local changes")

    if has_remote_branch:
        pull_result = git_repo(repo, ["pull", "--rebase", "--autostash", remote, remote_branch])
        if pull_result.returncode != 0:
            result["status"] = "failed"
            result["detail"] = f"pull failed on {remote}/{remote_branch}: {git_error(pull_result)}"
            return False, result

        result["pulled"] = True
        details.append(f"pulled {remote}/{remote_branch}")
    else:
        details.append(f"remote branch {remote}/{remote_branch} not found; skipping pull")

    push_command = ["push", remote, f"HEAD:{remote_branch}"]
    if not has_remote_branch:
        push_command.insert(1, "-u")

    push_result = git_repo(repo, push_command)
    if push_result.returncode != 0:
        result["status"] = "failed"
        result["detail"] = f"push failed on {remote}/{remote_branch}: {git_error(push_result)}"
        return False, result

    result["pushed"] = True
    details.append(f"pushed {remote}/{remote_branch}")
    result["status"] = "synced"
    result["detail"] = "; ".join(details)
    return True, result


def find_project_root(script_dir: Path) -> Path:
    return HELPERS.resolve_project_root(script_dir)


def emit_payload(payload: dict[str, object], json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(payload, indent=2))
        return

    status = str(payload.get("status") or "unknown")
    if status == "cached":
        age = payload.get("age_seconds")
        ttl_remaining = payload.get("ttl_remaining")
        print(
            f"[light-preflight] Fresh cache ({age}s old, {ttl_remaining}s remaining). Skipping repo sync."
        )
        return

    if status == "failed":
        print("[light-preflight] Lightweight prompt-start sync FAILED.")
    else:
        print("[light-preflight] Lightweight prompt-start sync complete.")

    for repo_result in payload.get("repos", []):
        repo_name = repo_result.get("name")
        repo_status = repo_result.get("status")
        detail = repo_result.get("detail") or ""
        prefix = "✓" if repo_status == "synced" else ("-" if repo_status == "skipped" else "!" )
        print(f"  {prefix} {repo_name}: {detail}")

    if payload.get("error"):
        print(f"[light-preflight] {payload['error']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a lightweight 60-minute repo sync for Lens prompt startup."
    )
    parser.add_argument("--ttl", type=int, default=3600, help="Cache TTL in seconds")
    parser.add_argument("--force", action="store_true", help="Ignore the timestamp and run sync now")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--governance-path", default="", help="Override the governance repo path")
    parser.add_argument(
        "--no-remote-probe",
        action="store_true",
        help="Skip the cheap ls-remote cache-invalidation probe (offline mode)",
    )
    args = HELPERS.parse_compat_args(parser)

    HELPERS.echo = (lambda msg: None) if args.json else print

    script_dir = Path(__file__).resolve().parent
    project_root = find_project_root(script_dir)
    active_personal_dir = HELPERS.migrate_legacy_personal_dir(project_root)
    governance_setup = HELPERS.ensure_governance_setup_file(project_root)

    governance_path: Path | None = None
    if args.governance_path:
        governance_path = HELPERS.resolve_workspace_path(project_root, args.governance_path)
    elif governance_setup.get("governance_repo_path"):
        governance_path = HELPERS.resolve_workspace_path(project_root, governance_setup["governance_repo_path"])

    timestamp_file = active_personal_dir / ".light-preflight-timestamp"
    now = datetime.now(tz=timezone.utc)
    cached_at = HELPERS.parse_timestamp(timestamp_file.read_text(encoding="utf-8")) if timestamp_file.is_file() else None
    if cached_at is not None and not args.force:
        age_seconds = int((now - cached_at).total_seconds())
        if age_seconds < args.ttl:
            bypass_reason: str | None = None
            if not args.no_remote_probe:
                control_new, control_detail = remote_has_new_commits(project_root)
                if control_new:
                    bypass_reason = f"control repo: {control_detail}"
                elif governance_path is not None and governance_path.is_dir():
                    preferred_branch = HELPERS.resolve_governance_branch(governance_path)
                    gov_new, gov_detail = remote_has_new_commits(
                        governance_path,
                        preferred_remote="origin",
                        preferred_branch=preferred_branch,
                    )
                    if gov_new:
                        bypass_reason = f"governance repo: {gov_detail}"

            if bypass_reason is None:
                payload = {
                    "status": "cached",
                    "cached_at": cached_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "age_seconds": age_seconds,
                    "ttl_seconds": args.ttl,
                    "ttl_remaining": args.ttl - age_seconds,
                    "ran_light_preflight": False,
                    "repos": [],
                }
                emit_payload(payload, args.json)
                return 0

            if not args.json:
                print(
                    f"[light-preflight] Cache invalidated ({bypass_reason}); running sync."
                )

    repo_results: list[dict[str, object]] = []

    control_ok, control_result = sync_repo(project_root, "control repo")
    repo_results.append(control_result)
    if not control_ok:
        payload = {
            "status": "failed",
            "cached_at": None,
            "age_seconds": None,
            "ttl_seconds": args.ttl,
            "ttl_remaining": None,
            "ran_light_preflight": True,
            "repos": repo_results,
            "error": f"control repo sync failed: {control_result['detail']}",
        }
        emit_payload(payload, args.json)
        return 1

    if governance_path is None:
        repo_results.append({
            "name": "governance repo",
            "path": None,
            "status": "skipped",
            "branch": None,
            "remote": None,
            "remote_branch": None,
            "committed": False,
            "pulled": False,
            "pushed": False,
            "detail": "governance repo not configured",
        })
    else:
        preferred_branch = HELPERS.resolve_governance_branch(governance_path) if governance_path.is_dir() else None
        governance_ok, governance_result = sync_repo(
            governance_path,
            "governance repo",
            preferred_branch=preferred_branch,
            preferred_remote="origin",
            allow_missing=True,
        )
        repo_results.append(governance_result)
        if not governance_ok:
            payload = {
                "status": "failed",
                "cached_at": None,
                "age_seconds": None,
                "ttl_seconds": args.ttl,
                "ttl_remaining": None,
                "ran_light_preflight": True,
                "repos": repo_results,
                "error": f"governance repo sync failed: {governance_result['detail']}",
            }
            emit_payload(payload, args.json)
            return 1

    written_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    timestamp_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp_file.write_text(written_at, encoding="utf-8")

    payload = {
        "status": "passed",
        "cached_at": written_at,
        "age_seconds": 0,
        "ttl_seconds": args.ttl,
        "ttl_remaining": args.ttl,
        "ran_light_preflight": True,
        "repos": repo_results,
    }
    emit_payload(payload, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())