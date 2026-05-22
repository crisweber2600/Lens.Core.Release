#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Interactively collect a GitHub PAT and export it as an environment variable.

NOTE: Python processes cannot persist environment variables to the parent shell.
To make the variable available in your current shell session, source the output:

    eval "$(uv run scripts/store-github-pat.py --export)"

Or use --export to get export commands you can paste manually.
"""

from __future__ import annotations

import argparse
import getpass
import re
import sys
from pathlib import Path


def load_yaml(path: Path) -> dict:
    import yaml  # noqa: PLC0415
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def detect_github_hosts(inventory_path: Path) -> list[str]:
    """Scan repo-inventory.yaml for GitHub-style remote URLs."""
    if not inventory_path.is_file():
        return ["github.com"]

    hosts: set[str] = set()
    data = load_yaml(inventory_path)
    for repo in data.get("repos", data.get("repositories", [])):
        url = ""
        for key in ("remote_url", "repo_url", "remote", "url"):
            if key in repo and repo[key]:
                url = str(repo[key])
                break
        # Extract hostname from HTTPS or SSH URLs
        m = re.match(r"^https?://([^/]+)/", url)
        if m:
            hosts.add(m.group(1))
        m = re.match(r"^git@([^:]+):", url)
        if m:
            hosts.add(m.group(1))

    # Filter to likely GitHub hosts
    github_hosts = [h for h in hosts if "github" in h.lower()]
    return github_hosts if github_hosts else ["github.com"]


def classify_host(host: str) -> tuple[str, str]:
    """Return (env_var_name, label) for a given host."""
    if host == "github.com":
        return "GITHUB_PAT", "GitHub.com"
    return "GH_ENTERPRISE_TOKEN", f"GitHub Enterprise ({host})"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interactively collect a GitHub PAT and print export commands."
    )
    parser.add_argument("--export", action="store_true", help="Print shell export commands (for eval)")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    _cwd = Path.cwd()
    project_root = (
        _cwd if (_cwd / "lens.core").exists()
        else next(p for p in script_dir.parents if (p / "lens.core").exists())
    )
    inventory_path = project_root / ".lens/repo-inventory.yaml"

    hosts = detect_github_hosts(inventory_path)

    exports: list[str] = []

    for host in hosts:
        env_var, label = classify_host(host)
        print(f"\nConfiguring PAT for {label}")
        print(f"  Environment variable: {env_var}")
        print(f"  Host:                 {host}")
        print()
        print("  Generate a PAT at:")
        if host == "github.com":
            print("    https://github.com/settings/tokens")
        else:
            print(f"    https://{host}/settings/tokens")
        print()

        try:
            pat = getpass.getpass(f"  Enter PAT for {host} (input hidden): ")
        except (KeyboardInterrupt, EOFError):
            print("\n[cancelled]")
            return 1

        if not pat.strip():
            print("  [skipped] Empty PAT — skipping this host.")
            continue

        exports.append(f"export {env_var}={pat.strip()}")
        print(f"  [ok] PAT accepted for {host}")

    if not exports:
        print("\n[warn] No PATs were collected.")
        return 1

    print()
    print("=" * 60)
    print("To apply PATs in your current shell, run:")
    print()
    for line in exports:
        print(f"  {line}")
    print()
    print("Or re-run with --export and pipe to eval:")
    print("  eval \"$(uv run scripts/store-github-pat.py --export)\"")
    print("=" * 60)

    if args.export:
        # Print raw export lines for eval ingestion
        for line in exports:
            print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
