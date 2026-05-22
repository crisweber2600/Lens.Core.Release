#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SAFE_PATH_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./: "
)


def _check_traversal(path: str) -> bool:
    """Return True if path is safe (no .. traversal)."""
    parts = Path(path).parts
    return ".." not in parts


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _out(data: dict, exit_code: int = 0) -> None:
    print(json.dumps(data))
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------

def cmd_preflight(args: argparse.Namespace) -> None:
    if not args.governance_dir:
        _out({"status": "error", "message": "--governance-dir is required"}, 1)

    if not _check_traversal(args.governance_dir):
        _out({"status": "error", "message": "Path traversal not allowed in governance-dir"}, 1)

    checks = []

    # Check git availability
    try:
        result = subprocess.run(
            ["git", "--version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            checks.append({"name": "git", "status": "ok", "message": result.stdout.strip()})
        else:
            checks.append({"name": "git", "status": "fail", "message": "git returned non-zero"})
    except FileNotFoundError:
        checks.append({"name": "git", "status": "fail", "message": "git not found on PATH"})

    # Check Python version
    major, minor = sys.version_info.major, sys.version_info.minor
    if major >= 3 and minor >= 10:
        checks.append({"name": "python", "status": "ok", "message": f"Python {major}.{minor}"})
    else:
        checks.append({
            "name": "python",
            "status": "fail",
            "message": f"Python 3.10+ required, found {major}.{minor}",
        })

    # Check governance dir
    gov_path = Path(args.governance_dir)
    if gov_path.exists() and any(gov_path.iterdir()):
        checks.append({
            "name": "governance_dir",
            "status": "warn",
            "message": f"Directory already exists and is non-empty: {args.governance_dir}",
        })
    else:
        checks.append({
            "name": "governance_dir",
            "status": "ok",
            "message": f"Path is available: {args.governance_dir}",
        })

    any_fail = any(c["status"] == "fail" for c in checks)
    overall = "fail" if any_fail else (
        "warn" if any(c["status"] == "warn" for c in checks) else "ok"
    )
    _out({"status": overall, "checks": checks}, 2 if overall == "warn" else (1 if any_fail else 0))


# ---------------------------------------------------------------------------
# scaffold
# ---------------------------------------------------------------------------

def cmd_scaffold(args: argparse.Namespace) -> None:
    if not args.governance_dir:
        _out({"status": "error", "message": "--governance-dir is required"}, 1)
    if not args.owner:
        _out({"status": "error", "message": "--owner is required"}, 1)

    if not _check_traversal(args.governance_dir):
        _out({"status": "error", "message": "Path traversal not allowed in governance-dir"}, 1)

    gov_path = Path(args.governance_dir)

    if gov_path.exists() and any(gov_path.iterdir()):
        _out({
            "status": "error",
            "message": f"Directory already exists: {args.governance_dir}. Use an empty or non-existent path.",
        }, 1)

    feature_index_content = "version: \"1\"\nfeatures: []\n"
    user_profile_content = f"# {args.owner}\n\nusername: {args.owner}\n"

    created = [
        "features/",
        "users/",
        f"users/{args.owner}.md",
        "feature-index.yaml",
    ]

    if args.dry_run:
        _out({
            "status": "ok",
            "created": created,
            "feature_index_path": str(gov_path / "feature-index.yaml"),
            "dry_run": True,
        })

    # Create directories
    (gov_path / "features").mkdir(parents=True, exist_ok=True)
    (gov_path / "users").mkdir(parents=True, exist_ok=True)

    # Write files atomically
    _atomic_write(gov_path / "users" / f"{args.owner}.md", user_profile_content)
    _atomic_write(gov_path / "feature-index.yaml", feature_index_content)

    # Git init
    git_cmds = [
        ["git", "init", str(gov_path)],
        ["git", "-C", str(gov_path), "checkout", "-b", "main"],
        ["git", "-C", str(gov_path), "add", "feature-index.yaml", f"users/{args.owner}.md"],
        ["git", "-C", str(gov_path), "commit", "-m", "chore: initialize Lens governance repo"],
    ]
    for cmd in git_cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # git checkout -b main may fail if branch already set; tolerate it
            if "checkout" in cmd and "already exists" in result.stderr:
                continue
            _out({
                "status": "error",
                "message": f"Git initialization failed: {result.stderr.strip()}",
            }, 1)

    _out({
        "status": "ok",
        "created": created,
        "feature_index_path": str(gov_path / "feature-index.yaml"),
    })


# ---------------------------------------------------------------------------
# write-config
# ---------------------------------------------------------------------------

def cmd_write_config(args: argparse.Namespace) -> None:
    if not args.governance_dir:
        _out({"status": "error", "message": "--governance-dir is required"}, 1)
    if not args.username:
        _out({"status": "error", "message": "--username is required"}, 1)

    if not _check_traversal(args.governance_dir):
        _out({"status": "error", "message": "Path traversal not allowed in governance-dir"}, 1)

    gov_path = Path(args.governance_dir)
    repos = [r.strip() for r in (args.target_repos or "").split(",") if r.strip()]

    profile_lines = [
        f"# {args.username}",
        "",
        f"username: {args.username}",
        f"default_ide: {args.default_ide or 'cursor'}",
        f"default_track: {args.default_track or 'full'}",
        f"theme: {args.theme or 'default'}",
        "target_repos:",
    ]
    for repo in repos:
        profile_lines.append(f"  - {repo}")
    profile_content = "\n".join(profile_lines) + "\n"

    config_data = {
        "github_pat": args.github_pat or "",
        "username": args.username,
        "default_ide": args.default_ide or "cursor",
        "target_repos": repos,
        "default_track": args.default_track or "full",
        "theme": args.theme or "default",
    }
    config_content = yaml.dump(config_data, default_flow_style=False, sort_keys=True)

    profile_path = gov_path / "users" / f"{args.username}.md"
    config_path = gov_path / "_bmad" / "config.user.yaml"

    files_written = [
        str(profile_path.relative_to(gov_path)),
        str(config_path.relative_to(gov_path)),
    ]

    if args.dry_run:
        _out({
            "status": "ok",
            "files_written": files_written,
            "dry_run": True,
            "preview": {
                files_written[0]: profile_content,
                files_written[1]: config_content,
            },
        })

    _atomic_write(profile_path, profile_content)
    _atomic_write(config_path, config_content)

    _out({"status": "ok", "files_written": files_written})


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Lens onboarding operations")
    sub = parser.add_subparsers(dest="command")

    p_pre = sub.add_parser("preflight")
    p_pre.add_argument("--governance-dir")

    p_sc = sub.add_parser("scaffold")
    p_sc.add_argument("--governance-dir")
    p_sc.add_argument("--owner")
    p_sc.add_argument("--dry-run", action="store_true")

    p_wc = sub.add_parser("write-config")
    p_wc.add_argument("--governance-dir")
    p_wc.add_argument("--username")
    p_wc.add_argument("--github-pat", default="")
    p_wc.add_argument("--default-ide", default="cursor")
    p_wc.add_argument("--target-repos", default="")
    p_wc.add_argument("--default-track", default="full")
    p_wc.add_argument("--theme", default="default")
    p_wc.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "preflight":
        cmd_preflight(args)
    elif args.command == "scaffold":
        cmd_scaffold(args)
    elif args.command == "write-config":
        cmd_write_config(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
