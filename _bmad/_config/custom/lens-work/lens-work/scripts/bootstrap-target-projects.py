#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Bootstrap TargetProjects by cloning, verifying, or syncing repos from repo-inventory.yaml."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def load_yaml(path: Path) -> dict:
    import yaml  # noqa: PLC0415
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def find_key(d: dict, *keys: str) -> str:
    for k in keys:
        if k in d and d[k]:
            return str(d[k])
    return ""


def resolve_dest(target_root: Path, local_path: str, name: str) -> Path:
    """Resolve repo-inventory local_path values consistently from project root."""
    if local_path:
        candidate = Path(local_path)
        if candidate.is_absolute():
            return candidate
        if candidate.parts and candidate.parts[0] == target_root.name:
            return target_root.parent / candidate
        return target_root / candidate
    return target_root / name


def git_clone(url: str, dest: Path, dry_run: bool) -> dict:
    if dry_run:
        return {"action": "clone", "url": url, "dest": str(dest), "dry_run": True}
    result = subprocess.run(
        ["git", "clone", url, str(dest)],
        capture_output=True, text=True,
    )
    return {
        "action": "clone",
        "url": url,
        "dest": str(dest),
        "success": result.returncode == 0,
        "error": result.stderr.strip() if result.returncode != 0 else None,
    }


def git_verify(dest: Path) -> dict:
    result = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    return {
        "action": "verify",
        "dest": str(dest),
        "success": result.returncode == 0,
    }


def git_sync(dest: Path, dry_run: bool) -> dict:
    verify = git_verify(dest)
    if not verify.get("success"):
        return {
            "action": "sync",
            "dest": str(dest),
            "success": False,
            "error": "not a git repository",
        }
    if dry_run:
        return {"action": "sync", "dest": str(dest), "dry_run": True, "success": True}
    result = subprocess.run(
        ["git", "-C", str(dest), "pull", "--ff-only"],
        capture_output=True,
        text=True,
    )
    return {
        "action": "sync",
        "dest": str(dest),
        "success": result.returncode == 0,
        "error": result.stderr.strip() if result.returncode != 0 else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clone or verify repos listed in repo-inventory.yaml."
    )
    parser.add_argument("--inventory-path", required=True, help="Path to repo-inventory.yaml")
    parser.add_argument("--target-root", default="TargetProjects", help="Root dir for clones")
    parser.add_argument("--sync-existing", action="store_true", help="Pull updates for existing repos")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    inventory_path = Path(args.inventory_path)
    if not inventory_path.is_file():
        msg = f"Inventory not found: {inventory_path}"
        if args.json:
            print(json.dumps({"error": msg}, indent=2))
        else:
            print(f"[error] {msg}", file=sys.stderr)
        return 1

    data = load_yaml(inventory_path)
    repos: list[dict] = data.get("repos", data.get("repositories", []))

    target_root = Path(args.target_root).resolve()
    results: list[dict] = []
    errors = 0

    for repo in repos:
        name = find_key(repo, "name")
        url = find_key(repo, "remote_url", "repo_url", "remote", "url")
        local = find_key(repo, "local_path", "clone_path", "path")

        if not url:
            results.append({"name": name, "error": "no url found"})
            errors += 1
            continue

        dest = resolve_dest(target_root, local, name)
        if dest.is_dir():
            if args.sync_existing:
                result = git_sync(dest, args.dry_run)
            else:
                result = git_verify(dest)
            if not result.get("success"):
                errors += 1
        else:
            result = git_clone(url, dest, args.dry_run)
            if not args.dry_run and not result.get("success"):
                errors += 1

        result["name"] = name
        results.append(result)

    if args.json:
        print(json.dumps({"repos": results, "errors": errors}, indent=2))
    else:
        for r in results:
            status = "DRY-RUN" if r.get("dry_run") else ("OK" if r.get("success", True) else "FAIL")
            action = r.get("action", "?")
            print(f"  [{status}] {r.get('name', '?')}  ({action})  → {r.get('dest', '')}")
        if errors:
            print(f"\n[warn] {errors} error(s) occurred.")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
