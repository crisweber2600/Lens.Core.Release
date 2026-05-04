#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Synchronise authority repos and validate workspace state before workflow execution."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def echo(msg: str) -> None:
    print(msg)


def git_repo(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )


def git_error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"


GOVERNANCE_AUTO_SYNC_COMMIT_MESSAGE = "chore(governance): auto-sync local changes"


def git_pull(repo: Path) -> bool:
    result = git_repo(repo, ["pull", "origin"])
    return result.returncode == 0


def git_current_branch(repo: Path) -> str:
    result = git_repo(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    return result.stdout.strip()


def git_branch_exists(repo: Path, branch: str, *, remote: bool = False) -> bool:
    ref = f"refs/remotes/origin/{branch}" if remote else f"refs/heads/{branch}"
    return git_repo(repo, ["show-ref", "--verify", "--quiet", ref]).returncode == 0


def git_has_clean_worktree(repo: Path) -> tuple[bool, str | None]:
    result = git_repo(repo, ["status", "--short"])
    if result.returncode != 0:
        return False, git_error(result)
    if result.stdout.strip():
        return False, "local changes present"
    return True, None


def auto_commit_local_changes(repo: Path) -> tuple[bool, str]:
    add_result = git_repo(repo, ["add", "-A"])
    if add_result.returncode != 0:
        return False, f"failed to stage local changes: {git_error(add_result)}"

    staged_result = git_repo(repo, ["diff", "--cached", "--quiet"])
    if staged_result.returncode == 0:
        return False, "local changes were detected but none could be staged for commit"
    if staged_result.returncode != 1:
        return False, f"failed to inspect staged changes: {git_error(staged_result)}"

    commit_result = git_repo(repo, ["commit", "-m", GOVERNANCE_AUTO_SYNC_COMMIT_MESSAGE])
    if commit_result.returncode != 0:
        return False, f"failed to commit local changes: {git_error(commit_result)}"

    sha_result = git_repo(repo, ["rev-parse", "--short", "HEAD"])
    sha = sha_result.stdout.strip() if sha_result.returncode == 0 else ""
    detail = "committed local changes"
    if sha:
        detail = f"{detail} ({sha})"
    return True, detail


def resolve_governance_branch(repo: Path) -> str:
    if git_branch_exists(repo, "main") or git_branch_exists(repo, "main", remote=True):
        return "main"

    result = git_repo(repo, ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"])
    if result.returncode == 0:
        ref = result.stdout.strip()
        if ref.startswith("origin/"):
            return ref.removeprefix("origin/")

    branch = git_current_branch(repo)
    return branch if branch and branch != "HEAD" else "main"


def ensure_local_branch(repo: Path, branch: str) -> tuple[bool, str | None]:
    if git_current_branch(repo) == branch:
        return True, None

    result = git_repo(repo, ["checkout", branch])
    if result.returncode == 0:
        return True, None

    if git_branch_exists(repo, branch, remote=True):
        result = git_repo(repo, ["checkout", "-B", branch, f"origin/{branch}"])
        if result.returncode == 0:
            return True, None

    return False, git_error(result)


def commits_ahead_of_origin(repo: Path, branch: str) -> tuple[int, str | None]:
    result = git_repo(repo, ["rev-list", "--count", f"origin/{branch}..HEAD"])
    if result.returncode != 0:
        return 0, git_error(result)

    try:
        return int(result.stdout.strip() or "0"), None
    except ValueError:
        return 0, f"unable to parse ahead count: {result.stdout.strip()}"


def sync_governance_repo(governance_repo: Path) -> tuple[bool, str]:
    worktree_check = git_repo(governance_repo, ["rev-parse", "--is-inside-work-tree"])
    if worktree_check.returncode != 0 or worktree_check.stdout.strip() != "true":
        return False, f"not a git worktree ({git_error(worktree_check)})"

    branch = resolve_governance_branch(governance_repo)
    active_branch = git_current_branch(governance_repo) or "HEAD"
    clean, clean_detail = git_has_clean_worktree(governance_repo)
    if not clean:
        if clean_detail == "local changes present" and active_branch != branch:
            return False, (
                f"local changes present on {active_branch}; switch to {branch} or clean the repo "
                "before automatic governance sync"
            )
        if clean_detail == "local changes present":
            pass
        else:
            return False, clean_detail or "unable to inspect worktree"

    sync_notes = [f"synced {branch}"]

    checked_out, checkout_detail = ensure_local_branch(governance_repo, branch)
    if not checked_out:
        return False, f"failed to checkout {branch}: {checkout_detail}"

    if not clean:
        committed, commit_detail = auto_commit_local_changes(governance_repo)
        if not committed:
            return False, commit_detail
        sync_notes.append(commit_detail)

    pull_result = git_repo(governance_repo, ["pull", "--rebase", "--autostash", "origin", branch])
    if pull_result.returncode != 0:
        return False, f"pull failed on {branch}: {git_error(pull_result)}"

    ahead, ahead_detail = commits_ahead_of_origin(governance_repo, branch)
    if ahead_detail:
        return False, ahead_detail

    if ahead > 0:
        push_result = git_repo(governance_repo, ["push", "origin", f"HEAD:{branch}"])
        if push_result.returncode != 0:
            return False, f"push failed on {branch}: {git_error(push_result)}"
        sync_notes.append(f"pushed {ahead} local commit(s)")

    return True, "; ".join(sync_notes)


def current_branch() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_hash_manifest(path: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if not path.is_file():
        return hashes
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([0-9a-fA-F]+)\s{2}(.+)$", line)
        if m:
            hashes[m.group(2)] = m.group(1).lower()
    return hashes


def remove_empty_parent_dirs(start_dir: Path, stop_dir: Path) -> None:
    current = start_dir
    while current != stop_dir and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def lens_dir(project_root: Path) -> Path:
    return project_root / ".lens"


def lens_version_file(project_root: Path) -> Path:
    return lens_dir(project_root) / "LENS_VERSION"


def legacy_lens_version_file(project_root: Path) -> Path:
    return project_root / "LENS_VERSION"


def personal_dir(project_root: Path) -> Path:
    return lens_dir(project_root) / "personal"


def legacy_personal_dir(project_root: Path) -> Path:
    return project_root / ".github" / "lens" / "personal"


PERSONAL_ARTIFACT_NAMES = (".github-hashes", ".preflight-timestamp", "context.yaml", "profile.yaml")


def relocate_root_personal_files(project_root: Path, active_dir: Path) -> None:
    active_root = lens_dir(project_root)
    active_root.mkdir(parents=True, exist_ok=True)
    active_dir.mkdir(parents=True, exist_ok=True)

    relocated: list[str] = []
    removed_duplicates: list[str] = []
    conflicts: list[str] = []

    for name in PERSONAL_ARTIFACT_NAMES:
        source = active_root / name
        destination = active_dir / name

        if not source.is_file():
            continue

        try:
            if destination.is_file():
                if source.read_bytes() == destination.read_bytes():
                    source.unlink()
                    removed_duplicates.append(name)
                else:
                    conflicts.append(name)
                continue

            source.replace(destination)
            relocated.append(name)
        except OSError as exc:
            echo(f"  ⚠ Unable to relocate misplaced personal file {name}: {exc}")

    if relocated:
        echo(
            "[preflight] Relocated misplaced personal files from .lens root to .lens/personal: "
            + ", ".join(relocated)
        )
    if removed_duplicates:
        echo(
            "[preflight] Removed duplicate personal files from .lens root: "
            + ", ".join(removed_duplicates)
        )
    if conflicts:
        echo(
            "[preflight] Found conflicting personal files in .lens root; leaving them for manual cleanup: "
            + ", ".join(conflicts)
        )


def migrate_legacy_personal_dir(project_root: Path) -> Path:
    active_dir = personal_dir(project_root)
    active_root = lens_dir(project_root)
    legacy_dir = legacy_personal_dir(project_root)

    if active_dir.exists():
        if legacy_dir.exists():
            echo("[preflight] .lens/personal already exists; leaving the legacy personal directory untouched")
        relocate_root_personal_files(project_root, active_dir)
        return active_dir

    active_root.mkdir(parents=True, exist_ok=True)

    if not legacy_dir.exists():
        active_dir.mkdir(parents=True, exist_ok=True)
        relocate_root_personal_files(project_root, active_dir)
        return active_dir

    echo("[preflight] Migrating local personal state from the legacy personal directory to .lens/personal...")
    import shutil

    shutil.move(str(legacy_dir), str(active_dir))
    remove_empty_parent_dirs(legacy_dir.parent, project_root / ".github")
    echo("[preflight] Personal state migration complete")
    relocate_root_personal_files(project_root, active_dir)
    return active_dir


def ensure_lens_version_file(project_root: Path) -> str:
    active_file = lens_version_file(project_root)
    legacy_file = legacy_lens_version_file(project_root)

    if active_file.is_file():
        return active_file.read_text(encoding="utf-8").strip()

    if not legacy_file.is_file():
        return ""

    lens_dir(project_root).mkdir(parents=True, exist_ok=True)
    version = legacy_file.read_text(encoding="utf-8").strip()
    active_file.write_text(version, encoding="utf-8")
    echo("[preflight] Seeded .lens/LENS_VERSION from the legacy root LENS_VERSION file")
    return version


def governance_setup_file(project_root: Path) -> Path:
    return lens_dir(project_root) / "governance-setup.yaml"


def legacy_personal_governance_setup_file(project_root: Path) -> Path:
    return personal_dir(project_root) / "governance-setup.yaml"


def legacy_governance_setup_file(project_root: Path) -> Path:
    return project_root / "docs" / "lens-work" / "governance-setup.yaml"


def _read_scalar_yaml_value(content: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", content, re.MULTILINE)
    if not match:
        return None

    raw_value = match.group(1).strip()
    if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in ('"', "'"):
        return raw_value[1:-1]
    return raw_value


def load_governance_setup(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    values: dict[str, str] = {}
    for key in ("governance_repo_path", "governance_remote_url"):
        value = _read_scalar_yaml_value(content, key)
        if value:
            values[key] = value
    return values


def ensure_governance_setup_file(project_root: Path) -> dict[str, str]:
    active_file = governance_setup_file(project_root)
    legacy_personal_file = legacy_personal_governance_setup_file(project_root)
    legacy_file = legacy_governance_setup_file(project_root)

    if active_file.is_file():
        if legacy_personal_file.is_file():
            try:
                if active_file.read_bytes() == legacy_personal_file.read_bytes():
                    legacy_personal_file.unlink()
                    echo("[preflight] Removed duplicate legacy governance setup from .lens/personal/governance-setup.yaml")
                else:
                    echo("[preflight] Found conflicting legacy governance setup at .lens/personal/governance-setup.yaml; using .lens/governance-setup.yaml")
            except OSError as exc:
                echo(f"  ⚠ Unable to reconcile legacy governance setup file: {exc}")
        return load_governance_setup(active_file)

    for source_file, source_label, prune_parent in (
        (legacy_personal_file, ".lens/personal/governance-setup.yaml", False),
        (legacy_file, "docs/lens-work/governance-setup.yaml", True),
    ):
        if not source_file.is_file():
            continue

        try:
            contents = source_file.read_text(encoding="utf-8")
            active_file.parent.mkdir(parents=True, exist_ok=True)
            active_file.write_text(contents, encoding="utf-8")
            source_file.unlink()
            if prune_parent:
                remove_empty_parent_dirs(source_file.parent, project_root / "docs")
            echo(f"[preflight] Migrated governance setup from {source_label} to .lens/governance-setup.yaml")
        except OSError as exc:
            echo(f"  ⚠ Unable to migrate governance setup file: {exc}")
            return load_governance_setup(source_file)

        return load_governance_setup(active_file)

    bmadconfig_values = _load_bmadconfig_governance(project_root)
    if bmadconfig_values:
        return bmadconfig_values

    return {}


def _load_bmadconfig_governance(project_root: Path) -> dict[str, str]:
    """Fallback governance settings read from lens-work bmadconfig.yaml.

    Allows light-preflight and other callers to sync the governance repo even
    when the per-user .lens/governance-setup.yaml has not been created yet.
    """

    candidates = [
        project_root / "lens.core" / "_bmad" / "lens-work" / "bmadconfig.yaml",
        project_root / "_bmad" / "lens-work" / "bmadconfig.yaml",
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        values = load_governance_setup(candidate)
        if not values:
            continue
        resolved: dict[str, str] = {}
        for key, raw_value in values.items():
            resolved[key] = raw_value.replace("{project-root}", str(project_root))
        if resolved.get("governance_repo_path"):
            return resolved
    return {}


def resolve_workspace_path(project_root: Path, raw_path: str) -> Path:
    raw_path = raw_path.replace("{project-root}", str(project_root))
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else project_root / path


def parse_compat_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    args, extras = parser.parse_known_args()
    if not extras or extras == ["."]:
        return args

    parser.error(f"unrecognized arguments: {' '.join(extras)}")
    raise AssertionError("argparse parser.error should exit")


def resolve_project_root(script_dir: Path) -> Path:
    """Locate the workspace/control-repo root.

    Requires the workspace layout: a directory that contains
    lens.core/_bmad/lens-work/lifecycle.yaml.

    This function does not support standalone source-repo roots because
    preflight.py depends on the lens.core/ checkout for syncing operations.
    Invoke via light-preflight.py from a workspace root instead.
    """
    current = Path.cwd().resolve()
    script_dir = script_dir.resolve()

    candidates: list[Path] = []
    for start in (current, script_dir):
        for candidate in (start, *start.parents):
            if candidate not in candidates:
                candidates.append(candidate)

    for candidate in candidates:
        if (candidate / "lens.core" / "_bmad" / "lens-work" / "lifecycle.yaml").is_file():
            return candidate

    raise RuntimeError(
        "Unable to resolve project root: could not find "
        "lens.core/_bmad/lens-work/lifecycle.yaml. "
        "Run preflight from a workspace root that contains a lens.core/ checkout."
    )


def prune_stale_synced_github_files(
    project_root: Path,
    stored_hashes: dict[str, str],
    new_hashes: dict[str, str],
) -> int:
    github_root = project_root / ".github"
    removed = 0

    for rel_path in sorted(set(stored_hashes) - set(new_hashes)):
        if not rel_path.startswith(".github/"):
            continue

        local_file = project_root / rel_path
        if not local_file.is_file():
            continue

        local_file.unlink()
        removed += 1
        remove_empty_parent_dirs(local_file.parent, github_root)

    return removed


# ---------------------------------------------------------------------------
# Prompt catalog metadata — (experience, role)
# Kept in sync with setup.py. Unknown stems are always included.
# ---------------------------------------------------------------------------
_PROMPT_METADATA: dict[str, tuple[str, str | None]] = {
    "lens-adversarial-review":           ("full",  "any"),
    "lens-batch":                         ("both",  "any"),
    "lens-bmad-brainstorming":            ("full",  "plan"),
    "lens-bmad-code-review":              ("full",  "dev"),
    "lens-bmad-create-architecture":      ("full",  "plan"),
    "lens-bmad-create-epics-and-stories": ("full",  "plan"),
    "lens-bmad-create-prd":               ("full",  "plan"),
    "lens-bmad-create-story":             ("full",  "plan"),
    "lens-bmad-create-ux-design":         ("full",  "plan"),
    "lens-bmad-domain-research":          ("full",  "plan"),
    "lens-bmad-market-research":          ("full",  "plan"),
    "lens-bmad-product-brief":            ("full",  "plan"),
    "lens-bmad-quick-dev":                ("full",  "dev"),
    "lens-bmad-sprint-planning":          ("full",  "plan"),
    "lens-bmad-technical-research":       ("full",  "plan"),
    "lens-businessplan":                  ("both",  "plan"),
    "lens-complete":                      ("both",  "any"),
    "lens-constitution":                  ("full",  "admin"),
    "lens-dev":                           ("both",  "dev"),
    "lens-discover":                      ("both",  "any"),
    "lens-expressplan":                   ("both",  "any"),
    "lens-finalizeplan":                  ("both",  "plan"),
    "lens-help":                          ("both",  "any"),
    "lens-log-problem":                   ("full",  None),
    "lens-move-feature":                  ("full",  "plan"),
    "lens-new-domain":                    ("any",   "plan"),
    "lens-new-feature":                   ("both",  "any"),
    "lens-new-project":                   ("both",  "any"),
    "lens-new-service":                   ("both",  "any"),
    "lens-next":                          ("both",  "any"),
    "lens-preflight":                     ("both",  "any"),
    "lens-preplan":                       ("both",  "plan"),
    "lens-split-feature":                 ("both",  "plan"),
    "lens-switch":                        ("both",  "any"),
    "lens-techplan":                      ("both",  "plan"),
    "lens-theme":                         ("both",  "any"),
    "lens-upgrade":                       ("full",  "admin"),
}


def _should_include_prompt(stem: str, experience: str, role: str) -> bool:
    """Return True if a prompt should be present for the given profile."""
    meta = _PROMPT_METADATA.get(stem)
    if meta is None:
        return True  # unknown stem → always keep (forward-compatible)

    exp, prole = meta

    if experience == "lite" and exp == "full":
        return False

    if role == "admin":
        return True

    if prole == "admin":
        return False

    if role == "planner":
        return prole in ("plan", "any", None)
    if role == "dev":
        return prole in ("dev", "any", None)
    return True  # "both"


def _load_user_profile(project_root: Path) -> dict[str, str]:
    """Read .lens/personal/profile.yaml; return defaults if missing."""
    profile_path = personal_dir(project_root) / "profile.yaml"
    defaults: dict[str, str] = {"experience_mode": "full", "primary_role": "both"}
    if not profile_path.is_file():
        return defaults
    try:
        for line in profile_path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^(experience_mode|primary_role):\s*(.+)$", line.strip())
            if m:
                defaults[m.group(1)] = m.group(2).strip()
    except OSError:
        pass
    return defaults


def emit_onboard_next_steps(project_root: Path) -> None:
    """Print the role-aware next-step handoff for the /onboard prompt."""
    profile = _load_user_profile(project_root)
    role = profile.get("primary_role", "both").strip().lower()

    echo("")
    echo("[onboard] Next steps:")
    if role == "dev":
        echo("  1. Use /switch to load the feature you want to work on.")
        echo("  2. Then use /dev to continue implementation for that feature.")
    else:
        echo("  Use /switch to continue existing work.")
        echo("  Use /new-* to create new work.")
    echo("  Use /next anytime to get the recommended next command for the current context.")


def parse_timestamp(raw: str) -> datetime | None:
    val = raw.strip()
    if not val:
        return None
    # Unix epoch seconds
    if re.match(r"^\d+$", val):
        return datetime.fromtimestamp(int(val), tz=timezone.utc)
    # ISO-8601
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        echo(f"  ⚠ Ignoring invalid preflight timestamp: {val}")
        return None


def pull_window_seconds(branch: str) -> int:
    if branch.startswith("alpha"):
        return 3600
    if branch.startswith("beta"):
        return 10800
    return 86400


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Shared preflight: sync authority repos and validate workspace."
    )
    parser.add_argument("--skip-constitution", action="store_true")
    parser.add_argument("--caller", default="")
    parser.add_argument("--governance-path", default="")
    args = parse_compat_args(parser)

    script_dir = Path(__file__).resolve().parent
    project_root = resolve_project_root(script_dir)
    active_personal_dir = migrate_legacy_personal_dir(project_root)
    active_lens_dir = lens_dir(project_root)
    release_dir = project_root / "lens.core"
    timestamp_file = active_personal_dir / ".preflight-timestamp"
    hash_file = active_personal_dir / ".github-hashes"
    lifecycle_path = release_dir / "_bmad/lens-work/lifecycle.yaml"
    governance_setup = ensure_governance_setup_file(project_root)
    governance_path = None
    if args.governance_path:
        governance_path = resolve_workspace_path(project_root, args.governance_path)
    elif governance_setup.get("governance_repo_path"):
        governance_path = resolve_workspace_path(project_root, governance_setup["governance_repo_path"])
        echo("[preflight] Resolved governance repo from .lens/governance-setup.yaml")

    # Change to project root
    import os
    os.chdir(project_root)

    # ------------------------------------------------------------------
    # Step 1: Check release dir
    # ------------------------------------------------------------------
    echo("[preflight] Checking release branch...")
    if not release_dir.is_dir():
        echo(f"ERROR: lens.core directory not found at {release_dir}")
        return 1

    # ------------------------------------------------------------------
    # Step 1a: Enforce LENS_VERSION compatibility
    # ------------------------------------------------------------------
    echo("[preflight] Verifying LENS_VERSION compatibility...")
    if not lifecycle_path.is_file():
        echo(f"ERROR: lifecycle.yaml not found at {lifecycle_path}")
        return 1

    module_schema = ""
    for line in lifecycle_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("schema_version:"):
            module_schema = line.split(":", 1)[1].strip()
            break

    if not module_schema:
        echo("VERSION MISMATCH: lifecycle.yaml is missing or has empty 'schema_version:'. Run /lens-upgrade.")
        return 1

    control_version = ensure_lens_version_file(project_root)

    if not control_version or (control_version != module_schema and control_version != f"{module_schema}.0.0"):
        display_version = control_version or "missing"
        echo(f"VERSION MISMATCH: control repo is v{display_version}, module expects v{module_schema}. Run /lens-upgrade.")
        return 1

    echo(f"  ✓ LENS_VERSION v{control_version} matches module schema")

    # ------------------------------------------------------------------
    # Step 2: Determine pull strategy
    # ------------------------------------------------------------------
    needs_pull = True
    last_time: datetime | None = None
    release_sync_ok = True
    governance_sync_ok = True

    if timestamp_file.is_file():
        raw = timestamp_file.read_text(encoding="utf-8").strip()
        last_time = parse_timestamp(raw)

    if last_time is not None:
        elapsed = (datetime.now(tz=timezone.utc) - last_time).total_seconds()
        window = pull_window_seconds(current_branch())
        if elapsed < window:
            needs_pull = False
            echo(f"[preflight] Timestamp fresh ({int(elapsed)}s < {window}s) — skipping pulls")

    if needs_pull:
        echo("[preflight] Pulling authority repos...")
        if not git_pull(release_dir):
            release_sync_ok = False
            echo("  ⚠ Release repo pull failed (offline?)")

    if governance_path and governance_path.is_dir():
        governance_sync_ok, governance_detail = sync_governance_repo(governance_path)
        if governance_sync_ok:
            echo(f"  ✓ Governance repo {governance_detail}")
        else:
            echo(f"  ⚠ Governance repo sync skipped: {governance_detail}")

    # ------------------------------------------------------------------
    # Step 3: Sync .github/ from release repo (hash-based)
    # ------------------------------------------------------------------
    echo("[preflight] Syncing .github/ from release repo...")
    release_github = release_dir / ".github"
    if not release_github.is_dir():
        echo(f"ERROR: Missing authority folder: {release_github}")
        return 1

    local_github = project_root / ".github"
    local_github.mkdir(parents=True, exist_ok=True)

    stored_hashes = load_hash_manifest(hash_file)
    new_hashes: dict[str, str] = {}
    updated_count = 0

    for src_file in sorted(release_github.rglob("*")):
        if not src_file.is_file():
            continue
        rel = ".github/" + src_file.relative_to(release_github).as_posix()
        r_hash = sha256_file(src_file)
        s_hash = stored_hashes.get(rel, "")
        local_file = project_root / rel
        l_hash = sha256_file(local_file) if local_file.is_file() else ""

        if r_hash != s_hash or l_hash != r_hash:
            local_file.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(src_file, local_file)
            updated_count += 1

        new_hashes[rel] = r_hash

    stale_removed = prune_stale_synced_github_files(project_root, stored_hashes, new_hashes)

    # Write hash manifest
    hash_file.parent.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(
        "\n".join(f"{v}  {k}" for k, v in sorted(new_hashes.items())) + "\n",
        encoding="utf-8",
    )
    echo(f"  ✓ .github/ synced ({updated_count} file(s) updated)")
    if stale_removed:
        echo(f"  ✓ Removed {stale_removed} stale synced .github file(s)")

    # Prompt hygiene
    prompts_dir = project_root / ".github/prompts"
    if prompts_dir.is_dir():
        release_prompts = release_github / "prompts"
        for pf in list(prompts_dir.iterdir()):
            name = pf.name
            if re.match(r"^(?:lens|len)-.*\.prompt\.md$", name):
                if not (release_prompts / name).exists():
                    pf.unlink()
            elif name.endswith(".prompt.md"):
                pf.unlink()

        # Profile-aware prompt filtering
        profile = _load_user_profile(project_root)
        experience = profile.get("experience_mode", "full")
        role = profile.get("primary_role", "both")
        profile_removed = 0
        for pf in list(prompts_dir.iterdir()):
            name = pf.name
            if not re.match(r"^(?:lens|len)-.*\.prompt\.md$", name):
                continue
            stem = name[: -len(".prompt.md")]
            if not _should_include_prompt(stem, experience, role):
                pf.unlink()
                profile_removed += 1
        if profile_removed:
            echo(f"  ✓ Removed {profile_removed} prompt(s) excluded by profile (experience={experience}, role={role})")

    # Managed stale file hygiene (.github/**/lens-* and .github/**/len-*)
    managed_stale_removed = 0
    for local_file in sorted(local_github.rglob("*")):
        if not local_file.is_file():
            continue

        rel_path = local_file.relative_to(local_github)
        if (release_github / rel_path).is_file():
            continue

        if re.match(r"^(?:lens|len)-", local_file.name):
            local_file.unlink()
            managed_stale_removed += 1
            remove_empty_parent_dirs(local_file.parent, local_github)

    if managed_stale_removed:
        echo(f"  ✓ Removed {managed_stale_removed} stale managed .github file(s)")

    # ------------------------------------------------------------------
    # Step 3b: Sync agent entry points
    # ------------------------------------------------------------------
    for entry in ["CLAUDE.md"]:
        src = release_dir / entry
        if src.is_file():
            local = project_root / entry
            if not local.is_file():
                import shutil
                shutil.copy2(src, local)
                echo(f"  ✓ Synced {entry}")
            else:
                result = subprocess.run(
                    ["git", "-C", str(release_dir), "diff", "--name-only", "HEAD@{1}", "HEAD", "--", entry],
                    capture_output=True, text=True,
                )
                if result.stdout.strip():
                    import shutil
                    shutil.copy2(src, local)
                    echo(f"  ✓ Synced {entry}")

    # ------------------------------------------------------------------
    # Step 4: Verify authority repos
    # ------------------------------------------------------------------
    missing_repos = not release_dir.is_dir()
    if governance_path and not governance_path.is_dir():
        missing_repos = True

    if missing_repos:
        if args.caller == "onboard":
            echo("[preflight] Authority repos incomplete — continuing so /onboard can show next steps")
        else:
            echo("")
            echo("⚠️  Missing authority repos — this workspace needs onboarding first.")
            echo("")
            echo("  Re-run setup-control-repo.py if the governance clone is missing.")
            echo("  It takes about 2 minutes and only needs to run once.")
            echo("")
            echo("  Then run /new-project (or /new-domain for step-by-step setup) and retry this command.")
            return 1

    # ------------------------------------------------------------------
    # Step 6: Update timestamp
    # ------------------------------------------------------------------
    if needs_pull:
        if release_sync_ok and governance_sync_ok:
            timestamp_file.parent.mkdir(parents=True, exist_ok=True)
            timestamp_file.write_text(
                datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                encoding="utf-8",
            )
            echo("[preflight] Timestamp updated")
        else:
            echo("[preflight] Timestamp not updated because authority repo sync did not complete cleanly")

    echo("[preflight] Preflight complete ✓")
    if args.caller == "onboard":
        emit_onboard_next_steps(project_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
