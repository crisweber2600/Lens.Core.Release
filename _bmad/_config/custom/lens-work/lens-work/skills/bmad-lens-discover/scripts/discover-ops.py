#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""discover-ops.py — Repo inventory sync operations for lens-discover.

Sub-commands
------------
scan        Compare governance repo-inventory.yaml against TargetProjects on disk.
add-entry   Append a repository entry to repo-inventory.yaml (idempotent).
validate    Validate every entry in repo-inventory.yaml has required fields.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    import yaml  # noqa: PLC0415
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _save_yaml(path: Path, data: dict) -> None:
    import yaml  # noqa: PLC0415
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _get_repos_list(data: dict) -> list[dict]:
    """Accept both 'repositories:' (canonical) and 'repos:' (legacy) top-level keys."""
    return data.get("repositories", data.get("repos", []))


def _find_field(entry: dict, *keys: str) -> str:
    for k in keys:
        v = entry.get(k)
        if v:
            return str(v)
    return ""


def _resolve_repo_path(target_root: Path, local_path: str = "", name: str = "") -> Path | None:
    """Resolve inventory paths against either project root or TargetProjects root."""
    if local_path:
        candidate = Path(local_path)
        if candidate.is_absolute():
            return candidate.resolve()
        if candidate.parts and candidate.parts[0] == target_root.name:
            return (target_root.parent / candidate).resolve()
        return (target_root / candidate).resolve()
    if name:
        return (target_root / name).resolve()
    return None


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

def _scan_inventory(inventory_path: Path) -> list[dict]:
    """Return list of repo entries from the inventory file, or empty list if missing."""
    if not inventory_path.is_file():
        return []
    return _get_repos_list(_load_yaml(inventory_path))


def _scan_disk(target_root: Path, max_depth: int = 3) -> list[Path]:
    """Walk target_root up to max_depth levels and collect directories that contain .git/."""
    git_dirs: list[Path] = []
    target_root = target_root.resolve()

    def _walk(path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        if not path.is_dir():
            return
        if (path / ".git").exists():
            git_dirs.append(path)
            return  # don't descend into nested git repos
        try:
            for child in sorted(path.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    _walk(child, depth + 1)
        except PermissionError:
            pass

    _walk(target_root, 0)
    return git_dirs


def _detect_remote_url(repo_path: Path) -> str:
    """Return the origin remote URL for a local git repo, or ''."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def cmd_scan(args: argparse.Namespace) -> int:
    inventory_path = Path(args.inventory_path)
    target_root = Path(args.target_root).resolve()

    inventory_missing = not inventory_path.is_file()
    inv_entries = _scan_inventory(inventory_path)
    disk_repos = _scan_disk(target_root)

    # Inventory → keyed by resolved local_path (or derived name-based path)
    inv_by_local: dict[str, dict] = {}
    for entry in inv_entries:
        local = _find_field(entry, "local_path", "clone_path", "path")
        name = _find_field(entry, "name")
        resolved = _resolve_repo_path(target_root, local, name)
        if resolved:
            inv_by_local[str(resolved)] = entry

    # missing_from_disk: in inventory but directory not found on disk
    missing_from_disk: list[dict] = []
    already_cloned: list[dict] = []

    for entry in inv_entries:
        local = _find_field(entry, "local_path", "clone_path", "path")
        name = _find_field(entry, "name")
        resolved = _resolve_repo_path(target_root, local, name)
        if resolved and resolved.exists():
            already_cloned.append(entry)
        else:
            missing_from_disk.append(entry)

    # untracked: on disk but not referenced by any inventory entry
    untracked: list[dict] = []
    for repo_path in disk_repos:
        path_str = str(repo_path)
        if path_str not in inv_by_local:
            # Check if it matches by derived key from any entry without explicit local_path
            matched = False
            for entry in inv_entries:
                name = _find_field(entry, "name")
                local = _find_field(entry, "local_path", "clone_path", "path")
                resolved = _resolve_repo_path(target_root, local, name)
                if resolved and str(resolved) == path_str:
                    matched = True
                    break
            if not matched:
                remote_url = _detect_remote_url(repo_path)
                rel = repo_path.relative_to(target_root.parent) if repo_path.is_relative_to(target_root.parent) else repo_path
                untracked.append({
                    "name": repo_path.name,
                    "local_path": str(rel),
                    "remote_url": remote_url or "",
                })

    result = {
        "inventory_path": str(inventory_path),
        "inventory_missing": inventory_missing,
        "target_root": str(target_root),
        "already_cloned": already_cloned,
        "missing_from_disk": missing_from_disk,
        "untracked": untracked,
        "summary": {
            "in_inventory": len(inv_entries),
            "on_disk": len(disk_repos),
            "already_cloned": len(already_cloned),
            "missing_from_disk": len(missing_from_disk),
            "untracked": len(untracked),
        },
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        s = result["summary"]
        print(f"[discover] inventory={s['in_inventory']} | on_disk={s['on_disk']} | synced={s['already_cloned']} | missing={s['missing_from_disk']} | untracked={s['untracked']}")
        if result["inventory_missing"]:
            print(f"  [warn] repo-inventory.yaml not found at: {inventory_path}")
        if result["missing_from_disk"]:
            print("\nMissing from disk (in inventory, not cloned):")
            for e in result["missing_from_disk"]:
                name = _find_field(e, "name")
                url = _find_field(e, "remote_url", "repo_url", "remote", "url")
                local = _find_field(e, "local_path", "clone_path", "path")
                print(f"  - {name}  url={url}  local={local or '(auto)'}")
        if result["untracked"]:
            print("\nUntracked repos (on disk, not in inventory):")
            for u in result["untracked"]:
                print(f"  - {u['name']}  path={u['local_path']}  remote={u['remote_url'] or '(none)'}")

    return 0


# ---------------------------------------------------------------------------
# add-entry
# ---------------------------------------------------------------------------

def cmd_add_entry(args: argparse.Namespace) -> int:
    inventory_path = Path(args.inventory_path)

    if inventory_path.is_file():
        data = _load_yaml(inventory_path)
    else:
        data = {}

    # Normalise to always use 'repositories' key
    existing = _get_repos_list(data)
    if "repos" in data and "repositories" not in data:
        data["repositories"] = data.pop("repos")
    if "repositories" not in data:
        data["repositories"] = []

    # Idempotency check
    for entry in existing:
        if _find_field(entry, "name") == args.name:
            msg = f"Entry '{args.name}' already exists — no change."
            if args.json:
                print(json.dumps({"action": "skip", "name": args.name, "reason": "already_exists", "message": msg}, indent=2))
            else:
                print(f"  [skip] {msg}")
            return 0

    new_entry: dict = {"name": args.name, "remote_url": args.remote_url}
    if args.local_path:
        new_entry["local_path"] = args.local_path

    data["repositories"].append(new_entry)
    _save_yaml(inventory_path, data)

    if args.json:
        print(json.dumps({"action": "added", "name": args.name, "remote_url": args.remote_url, "local_path": args.local_path or None, "inventory_path": str(inventory_path)}, indent=2))
    else:
        print(f"  [added] {args.name} → {inventory_path}")

    return 0


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def cmd_validate(args: argparse.Namespace) -> int:
    inventory_path = Path(args.inventory_path)

    if not inventory_path.is_file():
        msg = f"Inventory not found: {inventory_path}"
        if args.json:
            print(json.dumps({"valid": False, "error": msg, "invalid_entries": []}, indent=2))
        else:
            print(f"  [error] {msg}", file=sys.stderr)
        return 1

    entries = _get_repos_list(_load_yaml(inventory_path))
    invalid: list[dict] = []

    for i, entry in enumerate(entries):
        issues = []
        if not _find_field(entry, "name"):
            issues.append("missing 'name'")
        if not _find_field(entry, "remote_url", "repo_url", "remote", "url"):
            issues.append("missing 'remote_url'")
        if issues:
            invalid.append({"index": i, "entry": entry, "issues": issues})

    result = {
        "valid": len(invalid) == 0,
        "total": len(entries),
        "invalid_count": len(invalid),
        "invalid_entries": invalid,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["valid"]:
            print(f"  [ok] All {result['total']} entries are valid.")
        else:
            print(f"  [warn] {result['invalid_count']} invalid entries in {inventory_path}:")
            for inv in invalid:
                print(f"    - entry[{inv['index']}]: {', '.join(inv['issues'])}  → {inv['entry']}")

    return 0 if result["valid"] else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Repo inventory sync operations for lens-discover.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # scan
    s = sub.add_parser("scan", help="Compare inventory vs TargetProjects on disk")
    s.add_argument("--inventory-path", required=True, help="Path to repo-inventory.yaml")
    s.add_argument("--target-root", required=True, help="Root directory to scan for git repos")
    s.add_argument("--json", action="store_true", help="Output as JSON")

    # add-entry
    a = sub.add_parser("add-entry", help="Append an entry to repo-inventory.yaml")
    a.add_argument("--inventory-path", required=True, help="Path to repo-inventory.yaml (created if absent)")
    a.add_argument("--name", required=True, help="Repository name identifier")
    a.add_argument("--remote-url", required=True, help="Git remote URL")
    a.add_argument("--local-path", default="", help="Optional local clone path (relative)")
    a.add_argument("--json", action="store_true", help="Output as JSON")

    # validate
    v = sub.add_parser("validate", help="Validate all entries in repo-inventory.yaml")
    v.add_argument("--inventory-path", required=True, help="Path to repo-inventory.yaml")
    v.add_argument("--json", action="store_true", help="Output as JSON")

    return p


def main() -> int:
    parser = _make_parser()
    args = parser.parse_args()

    if args.command == "scan":
        return cmd_scan(args)
    if args.command == "add-entry":
        return cmd_add_entry(args)
    if args.command == "validate":
        return cmd_validate(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
