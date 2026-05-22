#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Derive milestone, phase, PR state, and next-action for a given initiative."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def branch_exists(name: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", name],
        capture_output=True, text=True
    )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Derive initiative status from branch topology."
    )
    parser.add_argument("--root", required=True, help="Initiative root name")
    parser.add_argument("--lifecycle-path", required=True, help="Path to lifecycle.yaml (unused, for compat)")
    parser.add_argument("--track", default="", help="Optional track override")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    milestones = ["techplan", "finalizeplan", "dev-ready"]
    phases = ["preplan", "businessplan", "techplan", "finalizeplan"]

    current_milestone: str | None = None
    active_milestone_branch: str | None = None
    completed_milestones: list[str] = []

    for ms in reversed(milestones):
        ms_branch = f"{args.root}-{ms}"
        if branch_exists(ms_branch):
            if current_milestone is None:
                current_milestone = ms
                active_milestone_branch = ms_branch
            completed_milestones.append(ms)

    current_phase: str | None = None
    phase_branch: str | None = None
    pending_action = "Review branch state"
    pr_summary = "0"

    if current_milestone:
        for phase in phases:
            p_branch = f"{args.root}-{current_milestone}-{phase}"
            if branch_exists(p_branch):
                current_phase = phase
                phase_branch = p_branch
        pending_action = "Complete phase" if current_phase else "Start next phase"

    if args.json:
        print(json.dumps({
            "initiative": args.root,
            "milestone": current_milestone,
            "milestone_branch": active_milestone_branch,
            "phase": current_phase,
            "phase_branch": phase_branch,
            "pending_action": pending_action,
            "pr_summary": pr_summary,
            "completed_milestones": completed_milestones,
            "track": args.track if args.track else None,
        }, indent=2))
    else:
        print("Status derived")
        print(f"  Initiative:  {args.root}")
        print(f"  Milestone:   {current_milestone or 'none'}")
        print(f"  Phase:       {current_phase or 'none'}")
        print(f"  Action:      {pending_action}")
        print(f"  PRs:         {pr_summary}")
        print(f"  Completed:   {', '.join(completed_milestones)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
