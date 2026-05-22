#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Scan docs/lens-work/initiatives for active initiative-state.yaml files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def load_yaml_simple(path: Path) -> dict:
    """Import yaml lazily (available via PEP 723 dep)."""
    import yaml  # noqa: PLC0415
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def find_scope(rel_parts: list[str]) -> str:
    """Derive scope label from path depth below 'initiatives/'."""
    depth = len(rel_parts) - 1  # last segment is filename
    match depth:
        case 1:
            return "domain"
        case 2:
            return "service"
        case 3:
            return "feature"
        case _:
            return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan for active initiatives under docs/lens-work/initiatives."
    )
    parser.add_argument("--domain", default="", help="Optional domain filter")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    _cwd = Path.cwd()
    project_root = (
        _cwd if (_cwd / "lens.core").exists()
        else next(p for p in script_dir.parents if (p / "lens.core").exists())
    )
    initiatives_dir = project_root / "docs" / "lens-work" / "initiatives"

    if not initiatives_dir.is_dir():
        if args.json:
            print(json.dumps({"initiatives": [], "error": "initiatives directory not found"}, indent=2))
        else:
            print(f"[warn] initiatives directory not found: {initiatives_dir}", file=sys.stderr)
        return 0

    results: list[dict] = []

    for state_file in sorted(initiatives_dir.rglob("initiative-state.yaml")):
        rel = state_file.relative_to(initiatives_dir)
        parts = list(rel.parts)

        # Optional domain filter
        if args.domain and (not parts or parts[0] != args.domain):
            continue

        doc: dict = {}
        try:
            doc = load_yaml_simple(state_file)
        except Exception as exc:  # noqa: BLE001
            doc = {"_parse_error": str(exc)}

        status = str(doc.get("lifecycle_status", "unknown")).lower()
        if status not in {"active", "unknown"}:
            continue

        initiative = {
            "path": str(state_file),
            "relative": str(rel),
            "scope": find_scope(parts),
            "lifecycle_status": status,
            "initiative_root": doc.get("initiative_root", ""),
            "track": doc.get("track", ""),
        }

        # Derive domain/service/feature labels from path depth
        if len(parts) >= 1:
            initiative["domain"] = parts[0]
        if len(parts) >= 2:
            initiative["service"] = parts[1]
        if len(parts) >= 3:
            initiative["feature"] = parts[2]

        results.append(initiative)

    if args.json:
        print(json.dumps({"initiatives": results, "count": len(results)}, indent=2))
    else:
        if not results:
            print("No active initiatives found.")
        else:
            for item in results:
                root = item.get("initiative_root") or item.get("relative", "")
                print(f"  [{item['scope']}] {root}  status={item['lifecycle_status']}  track={item.get('track', '')}")
        print(f"\nTotal: {len(results)} active initiative(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
