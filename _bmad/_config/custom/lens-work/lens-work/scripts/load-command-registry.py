#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Parse module-help.csv and group commands; optionally resolve a fuzzy command match."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

NAV_CODES = {"SW", "ST", "NX", "DS", "NI"}
LIFECYCLE_PHASES = re.compile(r"^phase-([1-5]|express)$|^delegation$")


def classify_group(phase: str, code: str) -> str:
    if code in NAV_CODES:
        return "navigation"
    if LIFECYCLE_PHASES.match(phase.strip()):
        return "lifecycle"
    return "utility"


def derive_user_cmd(display_name: str) -> str:
    return "/" + display_name.strip().lower().replace(" ", "-")


def fuzzy_resolve(commands: list[dict], query: str) -> tuple[dict | None, str]:
    q = query.lower()
    if not q.startswith("/"):
        q = f"/{q}"

    # 1. Exact
    for cmd in commands:
        if cmd["command"] == q:
            return cmd, "exact"

    # 2. Prefix
    for cmd in commands:
        c = cmd["command"]
        if c.startswith(q) or q.startswith(c):
            return cmd, "prefix"

    # 3. Normalized (strip /-)
    norm_q = re.sub(r"[/\-]", "", q)
    for cmd in commands:
        norm_c = re.sub(r"[/\-]", "", cmd["command"])
        if norm_c == norm_q:
            return cmd, "normalized"

    return None, ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load and query the lens-work command registry from module-help.csv."
    )
    parser.add_argument("--csv-path", required=True, help="Path to module-help.csv")
    parser.add_argument("--resolve", default="", help="Fuzzy command to resolve")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.is_file():
        msg = f"CSV file not found: {csv_path}"
        if args.json:
            print(json.dumps({"error": msg}, indent=2))
        else:
            print(f"[error] {msg}", file=sys.stderr)
        return 1

    commands: list[dict] = []
    with open(csv_path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            display = row.get("display-name", "")
            code = row.get("menu-code", "")
            desc = row.get("description", "")
            phase = row.get("phase", "")
            group = classify_group(phase, code)
            commands.append({
                "command": derive_user_cmd(display),
                "code": code,
                "description": desc,
                "group": group,
                "phase": phase,
            })

    if not commands:
        msg = "module-help.csv is empty or unparseable"
        if args.json:
            print(json.dumps({"error": msg}, indent=2))
        else:
            print(f"[error] {msg}", file=sys.stderr)
        return 1

    match_obj: dict | None = None
    if args.resolve:
        found, match_type = fuzzy_resolve(commands, args.resolve)
        if found:
            match_obj = {"command": found["command"], "group": found["group"], "type": match_type}

    if args.json:
        entries = [{"command": c["command"], "code": c["code"], "description": c["description"], "group": c["group"]} for c in commands]
        print(json.dumps({"commands": entries, "count": len(commands), "match": match_obj}, indent=2))
    else:
        print("Command registry loaded")
        print(f"  Commands: {len(commands)}")
        nav = sum(1 for c in commands if c["group"] == "navigation")
        life = sum(1 for c in commands if c["group"] == "lifecycle")
        util = sum(1 for c in commands if c["group"] == "utility")
        print(f"  Groups: navigation({nav}), lifecycle({life}), utility({util})")
        if args.resolve:
            if match_obj:
                print(f"  Recovery: {match_obj['command']} ({match_obj['type']} match, {match_obj['group']})")
            else:
                print(f"  Recovery: no match for '{args.resolve}'")

    return 0


if __name__ == "__main__":
    sys.exit(main())
