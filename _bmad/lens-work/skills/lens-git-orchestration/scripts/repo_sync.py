#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Shared repo sync helpers owned by lens-git-orchestration.

These helpers centralize the git pull or reconcile primitives reused by prompt-start
preflight and other Lens lifecycle surfaces. They intentionally do not encode request
policy. Callers decide whether a given repo sync should be a no-op, warning, pull-only,
or blocking condition.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


INTERRUPTED_STATE_MARKERS: tuple[tuple[str, str], ...] = (
    ("MERGE_HEAD", "merge in progress"),
    ("CHERRY_PICK_HEAD", "cherry-pick in progress"),
    ("REVERT_HEAD", "revert in progress"),
    ("BISECT_LOG", "bisect in progress"),
    ("rebase-merge", "rebase in progress"),
    ("rebase-apply", "rebase in progress"),
)


def git_repo(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )


def git_error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"


def current_branch(repo: Path) -> str:
    result = git_repo(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


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


def git_branch_exists(repo: Path, branch: str, *, remote: bool = False) -> bool:
    ref = f"refs/remotes/origin/{branch}" if remote else f"refs/heads/{branch}"
    return git_repo(repo, ["show-ref", "--verify", "--quiet", ref]).returncode == 0


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


def git_has_clean_worktree(repo: Path) -> tuple[bool, str | None]:
    result = git_repo(repo, ["status", "--short"])
    if result.returncode != 0:
        return False, git_error(result)
    if result.stdout.strip():
        return False, "local changes present"
    return True, None


def resolve_governance_branch(repo: Path) -> str:
    if git_branch_exists(repo, "main") or git_branch_exists(repo, "main", remote=True):
        return "main"

    result = git_repo(repo, ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"])
    if result.returncode == 0:
        ref = result.stdout.strip()
        if ref.startswith("origin/"):
            return ref.removeprefix("origin/")

    branch = current_branch(repo)
    return branch if branch and branch != "HEAD" else "main"


def ensure_local_branch(repo: Path, branch: str) -> tuple[bool, str | None]:
    if current_branch(repo) == branch:
        return True, None

    result = git_repo(repo, ["checkout", branch])
    if result.returncode == 0:
        return True, None

    if git_branch_exists(repo, branch, remote=True):
        result = git_repo(repo, ["checkout", "-B", branch, f"origin/{branch}"])
        if result.returncode == 0:
            return True, None

    return False, git_error(result)


def resolve_sync_target(
    repo: Path,
    branch: str,
    preferred_remote: str | None = None,
) -> tuple[str, str, str] | tuple[None, None, str]:
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


def remote_branch_exists(repo: Path, remote: str, branch: str) -> tuple[bool, str | None]:
    result = git_repo(repo, ["ls-remote", "--exit-code", "--heads", remote, branch])
    if result.returncode == 0:
        return True, None
    if result.returncode == 2:
        return False, None
    return False, git_error(result)


def commits_ahead_of_remote(repo: Path, remote: str, branch: str) -> tuple[int, str | None]:
    result = git_repo(repo, ["rev-list", "--count", f"{remote}/{branch}..HEAD"])
    if result.returncode != 0:
        return 0, git_error(result)

    try:
        return int(result.stdout.strip() or "0"), None
    except ValueError:
        return 0, f"unable to parse ahead count: {result.stdout.strip()}"


def sync_release_repo(release_repo: Path) -> tuple[bool, str]:
    pull_result = git_repo(release_repo, ["pull", "origin"])
    if pull_result.returncode == 0:
        return True, "pulled origin"

    pull_error = git_error(pull_result)
    reset_result = git_repo(release_repo, ["reset", "--hard"])
    if reset_result.returncode != 0:
        return False, f"pull failed: {pull_error}; reset --hard failed: {git_error(reset_result)}"

    retry_result = git_repo(release_repo, ["pull", "origin"])
    if retry_result.returncode != 0:
        return False, (
            f"pull failed: {pull_error}; reset --hard succeeded; "
            f"retry pull failed: {git_error(retry_result)}"
        )

    return True, "pull blocked; reset --hard; pulled origin"