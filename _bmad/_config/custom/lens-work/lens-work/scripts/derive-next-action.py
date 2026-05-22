#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Apply lifecycle decision rules to determine the next command or hard gate."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml


def read_yaml_field(path: Path, field: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(field)}:\s*(.+)", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Derive next action from initiative-state.yaml."
    )
    parser.add_argument("--initiative-root", required=True, help="Path to initiative root")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    state_file = Path(args.initiative_root) / "initiative-state.yaml"
    if not state_file.exists():
        print(f"ERROR: initiative-state.yaml not found in {args.initiative_root}", file=sys.stderr)
        return 1

    milestone = read_yaml_field(state_file, "milestone")
    phase = read_yaml_field(state_file, "phase")
    action = read_yaml_field(state_file, "action")
    scope = read_yaml_field(state_file, "scope")

    next_command: str | None = None
    gate_message: str | None = None
    hard_gate = False

    if not milestone and not phase and not action:
        gate_message = "Not currently on an initiative branch. Run /switch to load a feature or /dashboard to review the portfolio."
    elif not milestone and scope == "domain":
        next_command = "/new-service"
    elif not milestone and scope == "service":
        next_command = "/new-feature"
    elif re.search(r"awaiting review|awaiting merge", action, re.IGNORECASE):
        hard_gate = True
        gate_message = "A PR is still open for the active lifecycle step. Merge it, then run /next again."
    elif re.search(r"address review feedback", action, re.IGNORECASE):
        hard_gate = True
        gate_message = "Review feedback is blocking progress. Resolve the requested changes, then run /next again."
    elif action == "Ready to promote":
        gate_message = "Milestone promotion is no longer a direct Lens command. Run /next for the current lifecycle recommendation and continue from the suggested step."
    elif re.search(r"promotion in review", action, re.IGNORECASE):
        hard_gate = True
        gate_message = "A promotion PR is still open. Merge it, then run /next again."
    elif phase and re.search(r"complete phase|start next phase", action, re.IGNORECASE):
        next_command = f"/{phase}"
    elif re.search(r"ready for execution", action, re.IGNORECASE):
        gate_message = "All caught up. The initiative is ready for execution."
    else:
        gate_message = "No deterministic next action was found. Run /dashboard for the broader picture or /help for available commands."

    if args.json:
        print(json.dumps({
            "next_command": next_command,
            "gate_message": gate_message,
            "hard_gate": hard_gate,
        }, indent=2))
    else:
        print()
        if next_command:
            print(f"Next action: {next_command}")
        elif hard_gate:
            print(f"BLOCKED: {gate_message}")
        elif gate_message:
            print(f"Info: {gate_message}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
