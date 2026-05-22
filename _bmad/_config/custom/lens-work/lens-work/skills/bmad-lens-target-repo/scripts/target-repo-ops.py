#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""target-repo-ops.py — Provision feature target repos."""

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
from urllib.parse import urlparse

import yaml


REPO_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
VALID_VISIBILITIES = {"public", "private", "internal"}
VALID_DEV_BRANCH_MODES = {"direct-default", "feature-id", "feature-id-username"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def atomic_write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.dump(data, handle, default_flow_style=False, sort_keys=False, allow_unicode=True)
        os.replace(tmp_path, str(path))
    except Exception:
        os.unlink(tmp_path)
        raise


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def get_repos_list(data: dict) -> list[dict]:
    return data.get("repositories", data.get("repos", []))


def find_feature(governance_repo: Path, feature_id: str) -> Path | None:
    features_dir = governance_repo / "features"
    if not features_dir.exists():
        return None
    for yaml_file in features_dir.rglob("feature.yaml"):
        try:
            if load_yaml(yaml_file).get("featureId") == feature_id:
                return yaml_file
        except OSError:
            continue
    return None


def resolve_project_root(governance_repo: Path) -> Path:
    for candidate in [governance_repo, *governance_repo.parents]:
        if candidate.name == "TargetProjects":
            return candidate.parent
    raise ValueError("Could not derive project root from governance repo path; expected governance repo under TargetProjects/")


def derive_repo_name(value: str) -> str:
    stripped = str(value or "").strip().rstrip("/")
    if not stripped:
        return ""
    name = stripped.rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def normalize_dev_branch_mode(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in VALID_DEV_BRANCH_MODES:
        expected = ", ".join(sorted(VALID_DEV_BRANCH_MODES))
        raise ValueError(f"Invalid dev branch mode: {value!r}. Expected one of: {expected}")
    return normalized


def select_repo_entry(entries: list[dict], repo_name: str = "", local_path: str = "", remote_url: str = "") -> dict | None:
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if repo_name and entry.get("name") == repo_name:
            return entry
        if local_path and entry.get("local_path") == local_path:
            return entry
        entry_remote = entry.get("remote_url") or entry.get("url")
        if remote_url and entry_remote == remote_url:
            return entry

    if any((repo_name, local_path, remote_url)):
        return None

    for entry in entries:
        if isinstance(entry, dict):
            return entry
    return None


def normalize_local_path(project_root: Path, target_root: Path, local_path: str, domain: str, service: str, repo_name: str) -> str:
    if local_path:
        candidate = Path(local_path)
        if candidate.is_absolute():
            try:
                candidate = candidate.resolve().relative_to(project_root.resolve())
            except ValueError as exc:
                raise ValueError("local_path must stay inside the project root") from exc
        if candidate.parts and candidate.parts[0] == target_root.name:
            relative = candidate
        else:
            relative = Path(target_root.name) / candidate
    else:
        relative = Path(target_root.name) / domain / service / repo_name

    if ".." in relative.parts:
        raise ValueError("local_path must not contain path traversal")
    return relative.as_posix()


def derive_remote_url(base_url: str, owner: str, repo_name: str, remote_url: str) -> str:
    if remote_url:
        return remote_url.strip()
    if not owner:
        raise ValueError("owner is required when remote_url is not provided")
    return f"{base_url.rstrip('/')}/{owner}/{repo_name}"


def parse_repo_slug(remote_url: str, owner: str, repo_name: str) -> tuple[str, str]:
    if owner and repo_name:
        return owner, repo_name
    parsed = urlparse(remote_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2:
        derived_owner = owner or parts[-2]
        derived_repo = repo_name or derive_repo_name(parts[-1])
        return derived_owner, derived_repo
    raise ValueError("Could not derive owner/repo from remote_url; provide --owner explicitly")


def verify_remote(remote_url: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "ls-remote", remote_url, "HEAD"], capture_output=True, text=True)


def ensure_remote_repo(remote_url: str, owner: str, repo_name: str, base_url: str, visibility: str, create_remote: bool, dry_run: bool) -> dict:
    if dry_run and create_remote:
        repo_owner, repo_slug = parse_repo_slug(remote_url, owner, repo_name)
        command = [
            "gh",
            "repo",
            "create",
            f"{repo_owner}/{repo_slug}",
            f"--{visibility}",
            "--add-readme",
            "--disable-issues",
            "--description",
            f"Lens target repo for {repo_slug}",
        ]
        return {"status": "planned-create", "remote_url": remote_url, "command": " ".join(command)}

    check = verify_remote(remote_url)
    if check.returncode == 0:
        return {"status": "exists", "remote_url": remote_url}

    if not create_remote:
        raise RuntimeError(f"Remote repo is not reachable at {remote_url}; rerun with --create-remote or provide an existing --remote-url")

    parsed = urlparse(base_url)
    host = parsed.hostname or "github.com"
    if "github" not in host:
        raise RuntimeError("Automatic remote creation is supported for GitHub hosts only; create the repo manually and rerun")

    repo_owner, repo_slug = parse_repo_slug(remote_url, owner, repo_name)
    command = [
        "gh",
        "repo",
        "create",
        f"{repo_owner}/{repo_slug}",
        f"--{visibility}",
        "--add-readme",
        "--disable-issues",
        "--description",
        f"Lens target repo for {repo_slug}",
    ]
    if dry_run:
        return {"status": "planned-create", "remote_url": remote_url, "command": " ".join(command)}

    gh_check = subprocess.run(["which", "gh"], capture_output=True, text=True)
    if gh_check.returncode != 0:
        raise RuntimeError("GitHub CLI (gh) is required to auto-create a remote repo")

    env = dict(os.environ)
    if host != "github.com":
        env["GH_HOST"] = host

    result = subprocess.run(command, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create remote repo: {result.stderr.strip()}")

    verify = verify_remote(remote_url)
    if verify.returncode != 0:
        raise RuntimeError(f"Remote repo was created but is still not reachable at {remote_url}")
    return {"status": "created", "remote_url": remote_url, "command": " ".join(command)}


def clone_or_verify_local(dest: Path, remote_url: str, dry_run: bool) -> dict:
    if dest.exists():
        if not (dest / ".git").exists():
            raise RuntimeError(f"Local path exists but is not a git repo: {dest}")
        origin = subprocess.run(["git", "-C", str(dest), "remote", "get-url", "origin"], capture_output=True, text=True)
        if origin.returncode != 0:
            raise RuntimeError(f"Local repo exists but origin is missing: {dest}")
        if origin.stdout.strip() != remote_url:
            raise RuntimeError(f"Local repo origin mismatch at {dest}: expected {remote_url}, got {origin.stdout.strip()}")
        return {"status": "exists", "path": str(dest)}

    command = ["git", "clone", remote_url, str(dest)]
    if dry_run:
        return {"status": "planned-clone", "path": str(dest), "command": " ".join(command)}

    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to clone repo: {result.stderr.strip()}")
    return {"status": "cloned", "path": str(dest), "command": " ".join(command)}


def upsert_inventory(inventory_path: Path, entry: dict, dry_run: bool) -> dict:
    data = load_yaml(inventory_path) if inventory_path.exists() else {}
    if "repos" in data and "repositories" not in data:
        data["repositories"] = data.pop("repos")
    repos = get_repos_list(data)
    if "repositories" not in data:
        data["repositories"] = repos

    action = "added"
    for existing in repos:
        if existing.get("name") == entry["name"] or existing.get("local_path") == entry["local_path"] or existing.get("remote_url") == entry["remote_url"]:
            existing.update(entry)
            action = "updated"
            break
    else:
        repos.append(entry)

    if not dry_run:
        atomic_write_yaml(inventory_path, data)
    return {"status": action, "entry": entry}


def upsert_feature_target_repo(feature_path: Path, repo_entry: dict, dry_run: bool) -> dict:
    data = load_yaml(feature_path)
    target_repos = data.get("target_repos") or []

    action = "added"
    for existing in target_repos:
        if not isinstance(existing, dict):
            continue
        if existing.get("name") == repo_entry["name"] or existing.get("local_path") == repo_entry["local_path"] or existing.get("url") == repo_entry["url"]:
            existing.update(repo_entry)
            action = "updated"
            break
    else:
        target_repos.append(repo_entry)

    data["target_repos"] = target_repos
    data["updated"] = now_iso()
    if not dry_run:
        atomic_write_yaml(feature_path, data)
    return {"status": action, "entry": repo_entry}


def build_inventory_repo_entry(repo_name: str, remote_url: str, local_path: str, dev_branch_mode: str | None = None) -> dict:
    entry = {
        "name": repo_name,
        "remote_url": remote_url,
        "local_path": local_path,
    }
    if dev_branch_mode:
        entry["dev_branch_mode"] = dev_branch_mode
    return entry


def build_feature_repo_entry(
    repo_name: str,
    remote_url: str,
    local_path: str,
    default_branch: str,
    visibility: str,
    dev_branch_mode: str | None = None,
) -> dict:
    entry = {
        "name": repo_name,
        "url": remote_url,
        "remote_url": remote_url,
        "local_path": local_path,
        "branch": default_branch,
        "default_branch": default_branch,
        "visibility": visibility,
    }
    if dev_branch_mode:
        entry["dev_branch_mode"] = dev_branch_mode
    return entry


def cmd_provision(args: argparse.Namespace) -> dict:
    governance_repo = Path(args.governance_repo).resolve()
    feature_path = find_feature(governance_repo, args.feature_id)
    if not feature_path:
        return {"status": "fail", "error": f"Feature not found: {args.feature_id}"}

    if not REPO_NAME_PATTERN.match(args.repo_name):
        return {"status": "fail", "error": f"Invalid repo name: {args.repo_name}"}

    visibility = (args.visibility or "private").lower()
    if visibility not in VALID_VISIBILITIES:
        return {"status": "fail", "error": f"Invalid visibility: {visibility}"}

    try:
        project_root = resolve_project_root(governance_repo)
    except ValueError as exc:
        return {"status": "fail", "error": str(exc)}

    target_root = project_root / "TargetProjects"
    feature = load_yaml(feature_path)
    domain = feature.get("domain")
    service = feature.get("service")
    if not domain or not service:
        return {"status": "fail", "error": "Feature is missing domain/service metadata"}

    try:
        remote_url = derive_remote_url(args.base_url, args.owner, args.repo_name, args.remote_url)
        local_path = normalize_local_path(project_root, target_root, args.local_path, domain, service, args.repo_name)
    except ValueError as exc:
        return {"status": "fail", "error": str(exc)}

    dest = project_root / local_path
    inventory_path = governance_repo / "repo-inventory.yaml"
    inventory_entry = build_inventory_repo_entry(args.repo_name, remote_url, local_path)
    feature_repo_entry = build_feature_repo_entry(args.repo_name, remote_url, local_path, args.default_branch, visibility)

    try:
        remote_result = ensure_remote_repo(remote_url, args.owner, args.repo_name, args.base_url, visibility, args.create_remote, args.dry_run)
        clone_result = clone_or_verify_local(dest, remote_url, args.dry_run)
        inventory_result = upsert_inventory(inventory_path, inventory_entry, args.dry_run)
        feature_result = upsert_feature_target_repo(feature_path, feature_repo_entry, args.dry_run)
    except RuntimeError as exc:
        return {
            "status": "fail",
            "error": str(exc),
            "feature_id": args.feature_id,
            "repo_name": args.repo_name,
            "local_path": local_path,
            "remote_url": remote_url,
        }

    return {
        "status": "pass",
        "feature_id": args.feature_id,
        "repo_name": args.repo_name,
        "domain": domain,
        "service": service,
        "remote": remote_result,
        "clone": clone_result,
        "inventory": inventory_result,
        "feature": feature_result,
        "local_path": local_path,
        "local_repo_path": str(dest),
        "inventory_path": str(inventory_path),
        "feature_path": str(feature_path),
        "dry_run": bool(args.dry_run),
    }


def cmd_set_dev_branch_mode(args: argparse.Namespace) -> dict:
    governance_repo = Path(args.governance_repo).resolve()
    feature_path = find_feature(governance_repo, args.feature_id)
    if not feature_path:
        return {"status": "fail", "error": f"Feature not found: {args.feature_id}"}

    try:
        dev_branch_mode = normalize_dev_branch_mode(args.mode)
    except ValueError as exc:
        return {"status": "fail", "error": str(exc)}

    feature = load_yaml(feature_path)
    target_repos = feature.get("target_repos") or []
    if not isinstance(target_repos, list) or not target_repos:
        return {"status": "fail", "error": "Feature has no target_repos to update"}

    selected_repo = select_repo_entry(
        target_repos,
        repo_name=args.repo_name,
        local_path=args.local_path,
        remote_url=args.remote_url,
    )
    if not selected_repo:
        return {"status": "fail", "error": "No matching target repo found for the supplied selectors"}

    repo_name = str(selected_repo.get("name") or derive_repo_name(selected_repo.get("url") or selected_repo.get("remote_url") or args.remote_url))
    remote_url = str(selected_repo.get("remote_url") or selected_repo.get("url") or args.remote_url or "").strip()
    local_path = str(selected_repo.get("local_path") or args.local_path or "").strip()
    if not repo_name or not remote_url or not local_path:
        return {
            "status": "fail",
            "error": "Target repo entry must include name, local_path, and url/remote_url before a repo-scoped dev branch mode can be stored",
        }

    inventory_path = governance_repo / "repo-inventory.yaml"
    inventory_entry = build_inventory_repo_entry(repo_name, remote_url, local_path, dev_branch_mode)
    feature_repo_entry = dict(selected_repo)
    feature_repo_entry["dev_branch_mode"] = dev_branch_mode

    inventory_result = upsert_inventory(inventory_path, inventory_entry, args.dry_run)
    feature_result = upsert_feature_target_repo(feature_path, feature_repo_entry, args.dry_run)

    return {
        "status": "pass",
        "feature_id": args.feature_id,
        "repo_name": repo_name,
        "local_path": local_path,
        "remote_url": remote_url,
        "dev_branch_mode": dev_branch_mode,
        "inventory": inventory_result,
        "feature": feature_result,
        "inventory_path": str(inventory_path),
        "feature_path": str(feature_path),
        "dry_run": bool(args.dry_run),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provision feature target repos.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    provision = subparsers.add_parser("provision", help="Create or register a target repo for a feature")
    provision.add_argument("--governance-repo", required=True, help="Path to the governance repo root")
    provision.add_argument("--feature-id", required=True, help="Feature identifier")
    provision.add_argument("--repo-name", required=True, help="Repository name to provision")
    provision.add_argument("--owner", default="", help="GitHub owner or organization used when deriving the remote URL")
    provision.add_argument("--remote-url", default="", help="Existing remote URL to verify or clone")
    provision.add_argument("--local-path", default="", help="Optional project-root-relative clone path")
    provision.add_argument("--base-url", default="https://github.com", help="Git provider base URL")
    provision.add_argument("--visibility", default="private", help="Remote visibility when creating a repo")
    provision.add_argument("--default-branch", default="main", help="Default branch to store in feature metadata")
    provision.add_argument("--create-remote", action="store_true", help="Create the remote repo when it is missing")
    provision.add_argument("--dry-run", action="store_true", help="Report planned actions without writing files")

    set_mode = subparsers.add_parser("set-dev-branch-mode", help="Persist a repo-scoped dev branch mode for a feature target repo")
    set_mode.add_argument("--governance-repo", required=True, help="Path to the governance repo root")
    set_mode.add_argument("--feature-id", required=True, help="Feature identifier")
    set_mode.add_argument("--mode", required=True, help="Repo-scoped dev branch mode: direct-default, feature-id, or feature-id-username")
    set_mode.add_argument("--repo-name", default="", help="Optional target repo name selector")
    set_mode.add_argument("--remote-url", default="", help="Optional target repo remote URL selector")
    set_mode.add_argument("--local-path", default="", help="Optional target repo local path selector")
    set_mode.add_argument("--dry-run", action="store_true", help="Report planned actions without writing files")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "provision": cmd_provision,
        "set-dev-branch-mode": cmd_set_dev_branch_mode,
    }
    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2)
    print()
    sys.exit(0 if result.get("status") == "pass" else 1)


if __name__ == "__main__":
    main()