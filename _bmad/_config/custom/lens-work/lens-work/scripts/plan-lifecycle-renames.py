#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Plan or apply branch renames from v2 audience tokens to v3 milestone names."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

# v2 audience token → v3 milestone name
V2_TO_V3: dict[str, str] = {
    "small": "techplan",
    "medium": "devproposal",
    "large": "sprintplan",
    "base": "dev-ready",
}


def list_branches() -> list[str]:
    result = subprocess.run(
        ["git", "branch", "--format=%(refname:short)"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    return [b.strip() for b in result.stdout.splitlines() if b.strip()]


def rename_branch(old: str, new: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["git", "branch", "-m", old, new],
        capture_output=True, text=True,
    )
    return result.returncode == 0, result.stderr.strip()


def compute_new_name(branch: str) -> str | None:
    """Return the v3 name for a branch if it contains a v2 audience token."""
    for v2, v3 in V2_TO_V3.items():
        # Match token as a dash-delimited segment
        pattern = rf"(^|-)({re.escape(v2)})(-|$)"
        match = re.search(pattern, branch)
        if match:
            replaced = branch[:match.start(2)] + v3 + branch[match.end(2):]
            return replaced
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or apply v2→v3 branch lifecycle renames."
    )
    parser.add_argument("--apply", action="store_true", help="Execute renames (default: dry-run)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    branches = list_branches()
    planned: list[dict] = []

    for branch in branches:
        new_name = compute_new_name(branch)
        if new_name and new_name != branch:
            planned.append({"old": branch, "new": new_name})

    if not planned:
        if args.json:
            print(json.dumps({"renames": [], "count": 0}, indent=2))
        else:
            print("No v2 audience token branches found to rename.")
        return 0

    results: list[dict] = []

    for item in planned:
        entry: dict = dict(item)
        if args.apply:
            ok, err = rename_branch(item["old"], item["new"])
            entry["success"] = ok
            if not ok:
                entry["error"] = err
        else:
            entry["dry_run"] = True
        results.append(entry)

    if args.json:
        print(json.dumps({
            "renames": results,
            "count": len(results),
            "applied": args.apply,
        }, indent=2))
    else:
        verb = "Renamed" if args.apply else "Would rename"
        for r in results:
            status = ""
            if args.apply:
                status = " OK" if r.get("success") else f" FAIL: {r.get('error', '')}"
            print(f"  {verb}: {r['old']} → {r['new']}{status}")
        if not args.apply:
            print("\nRun with --apply to execute renames.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
