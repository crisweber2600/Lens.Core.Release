#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Discover operations for Lens repo inventory drift checks.

The script owns deterministic inventory and disk-state operations only. It does
not perform git commits, pushes, network access, or interactive prompting.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml


MAX_SCAN_DEPTH = 3


def canonical_path(path: Path) -> Path:
    """Return a resolved path for all path equality checks."""
    return Path(path).expanduser().resolve()


def path_to_posix(path: Path) -> str:
    return Path(path).as_posix()


def normalize_inventory_key(data: dict[str, Any]) -> list[Any]:
    repositories = data.get("repositories")
    if repositories is None:
        repositories = data.get("repos", [])
    if repositories is None:
        return []
    if not isinstance(repositories, list):
        raise ValueError("inventory repositories must be a list")
    return repositories


def read_inventory(inventory_path: Path) -> tuple[dict[str, Any], list[Any]]:
    if not inventory_path.exists():
        return {}, []
    try:
        data = yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"failed to parse inventory YAML: {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("inventory must contain a YAML mapping")
    return data, normalize_inventory_key(data)


def atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False, allow_unicode=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def default_local_path(name: str) -> str:
    return f"TargetProjects/{name}"


def resolve_inventory_local_path(local_path: str, inventory_path: Path, target_root: Path) -> Path:
    raw_path = str(local_path).strip()
    if not raw_path:
        raw_path = "."

    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return canonical_path(candidate)

    normalized = raw_path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]

    project_root = canonical_path(target_root).parent
    if normalized == "TargetProjects" or normalized.startswith("TargetProjects/"):
        return canonical_path(project_root / Path(normalized))

    return canonical_path(inventory_path.parent / candidate)


def repo_display_local_path(repo_path: Path, target_root: Path) -> str:
    resolved_repo = canonical_path(repo_path)
    project_root = canonical_path(target_root).parent
    try:
        return path_to_posix(resolved_repo.relative_to(project_root))
    except ValueError:
        return path_to_posix(resolved_repo)


def is_git_repo_dir(path: Path) -> bool:
    return (path / ".git").exists()


def find_disk_repositories(target_root: Path) -> list[Path]:
    root = canonical_path(target_root)
    if not root.exists():
        return []

    found: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        if is_git_repo_dir(current):
            found.append(canonical_path(current))
            continue
        if depth >= MAX_SCAN_DEPTH:
            continue
        try:
            children = sorted(current.iterdir(), key=lambda child: child.name.lower())
        except OSError:
            continue
        for child in reversed(children):
            if child.name == ".git" or not child.is_dir():
                continue
            stack.append((child, depth + 1))
    return sorted(found, key=lambda path: path_to_posix(path).lower())


def get_origin_remote(repo_path: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    remote_url = result.stdout.strip()
    return remote_url or None


def entry_local_path(entry: dict[str, Any]) -> str:
    name = str(entry.get("name") or "").strip()
    return str(entry.get("local_path") or default_local_path(name)).strip()


def inventory_entry_payload(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": entry.get("name"),
        "remote_url": entry.get("remote_url"),
        "local_path": entry_local_path(entry),
    }


def scan_inventory(inventory_path: Path, target_root: Path) -> dict[str, Any]:
    _, entries = read_inventory(inventory_path)
    disk_repos = find_disk_repositories(target_root)
    disk_paths = {canonical_path(path) for path in disk_repos}

    inventory_paths: set[Path] = set()
    missing_from_disk: list[dict[str, Any]] = []
    already_cloned: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        local_path = entry_local_path(entry)
        resolved_path = resolve_inventory_local_path(local_path, inventory_path, target_root)
        inventory_paths.add(resolved_path)
        payload = inventory_entry_payload(entry)
        if resolved_path in disk_paths:
            already_cloned.append(payload)
        else:
            missing_from_disk.append(payload)

    untracked: list[dict[str, Any]] = []
    for repo_path in disk_repos:
        resolved_repo = canonical_path(repo_path)
        if resolved_repo in inventory_paths:
            continue
        payload = {
            "name": repo_path.name,
            "local_path": repo_display_local_path(repo_path, target_root),
        }
        remote_url = get_origin_remote(repo_path)
        if remote_url:
            payload["remote_url"] = remote_url
        untracked.append(payload)

    return {
        "missing_from_disk": missing_from_disk,
        "untracked": untracked,
        "already_cloned": already_cloned,
        "summary": {
            "missing_from_disk": len(missing_from_disk),
            "untracked": len(untracked),
            "already_cloned": len(already_cloned),
        },
    }


def add_inventory_entry(inventory_path: Path, name: str, remote_url: str, local_path: str | None) -> dict[str, Any]:
    normalized_name = name.strip()
    normalized_remote_url = remote_url.strip()
    normalized_local_path = local_path.strip() if local_path is not None else None

    data, entries = read_inventory(inventory_path)
    for entry in entries:
        if isinstance(entry, dict) and str(entry.get("remote_url") or "").strip() == normalized_remote_url:
            return {"added": False, "reason": "already_exists"}

    new_entry = {
        "name": normalized_name,
        "remote_url": normalized_remote_url,
        "local_path": normalized_local_path or default_local_path(normalized_name),
        "feature_base_branch": "",
    }
    canonical_entries = [entry for entry in entries]
    canonical_entries.append(new_entry)

    output = dict(data)
    output.pop("repos", None)
    output["repositories"] = canonical_entries
    atomic_write_yaml(inventory_path, output)
    return {"added": True, "reason": "new_entry", "entry": new_entry}


def validate_inventory(inventory_path: Path) -> dict[str, Any]:
    _, entries = read_inventory(inventory_path)
    errors: list[dict[str, Any]] = []

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append({"index": index, "name": None, "remote_url": None, "issue": "entry must be a mapping"})
            continue
        name = entry.get("name")
        remote_url = entry.get("remote_url")
        if not str(name or "").strip():
            errors.append({"index": index, "name": name, "remote_url": remote_url, "issue": "missing name"})
        if not str(remote_url or "").strip():
            errors.append({"index": index, "name": name, "remote_url": remote_url, "issue": "missing remote_url"})

    return {"valid": not errors, "errors": errors}


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(yaml.safe_dump(payload, sort_keys=True, allow_unicode=True), end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare and update Lens repo-inventory.yaml state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Compare inventory entries with TargetProjects disk state.")
    scan.add_argument("--inventory-path", required=True, type=Path)
    scan.add_argument("--target-root", required=True, type=Path)
    scan.add_argument("--json", action="store_true")

    add_entry = subparsers.add_parser("add-entry", help="Add an inventory entry idempotently by remote_url.")
    add_entry.add_argument("--inventory-path", required=True, type=Path)
    add_entry.add_argument("--name", required=True)
    add_entry.add_argument("--remote-url", required=True)
    add_entry.add_argument("--local-path")
    add_entry.add_argument("--json", action="store_true")

    validate = subparsers.add_parser("validate", help="Validate required inventory entry fields.")
    validate.add_argument("--inventory-path", required=True, type=Path)
    validate.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            payload = scan_inventory(args.inventory_path, args.target_root)
            emit(payload, args.json)
            return 0
        if args.command == "add-entry":
            payload = add_inventory_entry(args.inventory_path, args.name, args.remote_url, args.local_path)
            emit(payload, args.json)
            return 0
        if args.command == "validate":
            payload = validate_inventory(args.inventory_path)
            emit(payload, args.json)
            return 0 if payload["valid"] else 1
    except Exception as exc:
        payload = {"status": "fail", "error": str(exc)}
        emit(payload, getattr(args, "json", False))
        return 1
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())