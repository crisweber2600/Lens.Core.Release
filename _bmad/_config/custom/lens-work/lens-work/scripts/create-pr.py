#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.31"]
# ///
"""Create a GitHub PR using REST API (PAT auth) or print a manual URL."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


# ---------------------------------------------------------------------------
# Remote parsing
# ---------------------------------------------------------------------------

def get_remote_url(remote: str) -> str:
    result = subprocess.run(
        ["git", "remote", "get-url", remote],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Cannot get remote URL for '{remote}': {result.stderr.strip()}")
    return result.stdout.strip()


def parse_remote_url(url: str) -> dict:
    info: dict = {"host": None, "org": None, "project": None, "repo": None, "platform": "unknown"}

    # GitHub / generic HTTPS: https://host/org/repo[.git]
    m = re.match(r"^https?://([^/]+)/([^/]+)/([^/]+?)(?:\.git)?$", url)
    if m:
        info["host"] = m.group(1)
        info["org"] = m.group(2)
        info["repo"] = m.group(3)
        if "github" in info["host"]:
            info["platform"] = "github"
        return info

    # GitHub SSH: git@host:org/repo[.git]
    m = re.match(r"^git@([^:]+):([^/]+)/([^/]+?)(?:\.git)?$", url)
    if m:
        info["host"] = m.group(1)
        info["org"] = m.group(2)
        info["repo"] = m.group(3)
        if "github" in info["host"]:
            info["platform"] = "github"
        return info

    # AzDO HTTPS: https://dev.azure.com/org/project/_git/repo[.git]
    m = re.match(r"^https?://dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+?)(?:\.git)?$", url)
    if m:
        info.update({"host": "dev.azure.com", "org": m.group(1), "project": m.group(2), "repo": m.group(3), "platform": "azdo"})
        return info

    # AzDO SSH: git@ssh.dev.azure.com:v3/org/project/repo[.git]
    m = re.match(r"^git@ssh\.dev\.azure\.com:v3/([^/]+)/([^/]+)/([^/]+?)(?:\.git)?$", url)
    if m:
        info.update({"host": "dev.azure.com", "org": m.group(1), "project": m.group(2), "repo": m.group(3), "platform": "azdo"})
        return info

    return info


def get_pr_url(info: dict, source: str, target: str) -> str:
    if info["platform"] == "github" and info["host"] and info["org"] and info["repo"]:
        return f"https://{info['host']}/{info['org']}/{info['repo']}/compare/{target}...{source}"
    if info["platform"] == "azdo" and info["org"] and info["project"] and info["repo"]:
        return (
            f"https://dev.azure.com/{info['org']}/{info['project']}/_git/{info['repo']}"
            f"/pullrequestcreate?sourceRef={source}&targetRef={target}"
        )
    return f"MANUAL: Create PR from {source} -> {target}"


# ---------------------------------------------------------------------------
# Profile PAT lookup
# ---------------------------------------------------------------------------

def get_profile_pat(host: str, profile_file: Path) -> str | None:
    if not host or not profile_file.is_file():
        return None
    in_credentials = False
    current_host: str | None = None
    for line in profile_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "git_credentials:":
            in_credentials = True
            continue
        if in_credentials:
            m = re.match(r"^-?\s*host:\s*(.+)$", stripped)
            if m:
                current_host = m.group(1).strip()
                continue
            m = re.match(r"^pat:\s*(.+)$", stripped)
            if m and current_host == host:
                return m.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# GitHub API PR creation
# ---------------------------------------------------------------------------

def github_create_pr(info: dict, source: str, target: str, title: str, body: str, pat: str, timeout: int) -> dict:
    import requests  # noqa: PLC0415

    api_base = "https://api.github.com" if info["host"] == "github.com" else f"https://{info['host']}/api/v3"
    repo_name = f"{info['org']}/{info['repo']}"
    headers = {
        "Authorization": f"token {pat}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
    }
    payload = {"head": source, "base": target, "title": title, "body": body}

    try:
        resp = requests.post(f"{api_base}/repos/{repo_name}/pulls", headers=headers, json=payload, timeout=timeout)
        if resp.status_code in (200, 201):
            data = resp.json()
            return {"success": True, "url": data.get("html_url"), "number": data.get("number"), "id": data.get("id")}

        if resp.status_code == 422:
            print("  [WARN]  PR may already exist — HTTP 422", file=sys.stderr)
            # Look up existing PR
            head_param = quote(f"{info['org']}:{source}", safe="")
            base_param = quote(target, safe="")
            list_resp = requests.get(
                f"{api_base}/repos/{repo_name}/pulls?head={head_param}&base={base_param}&state=open",
                headers=headers, timeout=timeout,
            )
            if list_resp.status_code == 200:
                existing = list_resp.json()
                if existing:
                    pr = existing[0]
                    print(f"  [INFO]  Existing PR found: {pr.get('html_url')}", file=sys.stderr)
                    return {"success": True, "url": pr.get("html_url"), "number": pr.get("number"), "id": pr.get("id"), "existing": True}
            return {"success": False, "url": get_pr_url(info, source, target), "existing": True, "fallback": True, "error": f"HTTP 422"}

        print(f"  [ERROR] PR creation failed — HTTP {resp.status_code}", file=sys.stderr)
        return {"success": False, "url": None, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    except Exception as exc:  # noqa: BLE001
        return {"success": False, "url": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Create a PR via GitHub REST API or print a manual URL.")
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--target-branch", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--url-only", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    try:
        remote_url = get_remote_url(args.remote)
        info = parse_remote_url(remote_url)
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if info["platform"] == "unknown" or not info["host"]:
        print(f"[error] Unable to parse remote URL: {remote_url}", file=sys.stderr)
        return 1

    print(f"LENS PR Creation")
    print(f"  Source:   {args.source_branch}")
    print(f"  Target:   {args.target_branch}")
    print(f"  Title:    {args.title}")
    print(f"  Platform: {info['platform']}")
    print()

    if args.url_only:
        url = get_pr_url(info, args.source_branch, args.target_branch)
        print(f"PR URL:\n   {url}")
        return 0

    # Resolve PAT
    pat: str | None = None
    if info["host"]:
        # Try to find repo root for profile.yaml
        result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if result.returncode == 0:
            profile_file = Path(result.stdout.strip()) / ".lens/personal/profile.yaml"
            pat = get_profile_pat(info["host"], profile_file)

        if not pat:
            for env_var in ("GITHUB_TOKEN", "GH_TOKEN"):
                pat = os.environ.get(env_var)
                if pat:
                    print(f"  [INFO]  PAT loaded from environment: {env_var}", file=sys.stderr)
                    break

    if info["platform"] == "github":
        if pat:
            result_data = github_create_pr(info, args.source_branch, args.target_branch, args.title, args.body, pat, args.timeout)
        else:
            print("  [INFO]  No PAT available — providing manual PR URL")
            result_data = {"success": False, "url": get_pr_url(info, args.source_branch, args.target_branch), "manual": True}

        if result_data.get("success"):
            print(f"PR created successfully")
            print(f"   URL:    {result_data.get('url')}")
            print(f"   Number: #{result_data.get('number')}")
        elif result_data.get("manual") or result_data.get("fallback"):
            print(f"Manual PR creation required:")
            print(f"   {result_data.get('url')}")
        else:
            print(f"PR creation failed: {result_data.get('error')}", file=sys.stderr)
            return 1
    else:
        print(f"PR creation via API not yet implemented for {info['platform']}")
        print(f"   Visit: {get_pr_url(info, args.source_branch, args.target_branch)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
