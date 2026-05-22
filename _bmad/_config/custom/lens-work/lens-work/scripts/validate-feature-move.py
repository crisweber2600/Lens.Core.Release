#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Validate that a feature can be safely moved to a new domain/service."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that a feature can be safely moved to a new domain/service."
    )
    parser.add_argument("--feature", required=True, help="Feature name")
    parser.add_argument("--old-domain", required=True, help="Source domain")
    parser.add_argument("--old-service", required=True, help="Source service")
    parser.add_argument("--new-domain", required=True, help="Target domain")
    parser.add_argument("--new-service", required=True, help="Target service")
    parser.add_argument("--initiatives-root", required=True, help="Path to initiatives root")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Sanitize inputs
    new_domain = re.sub(r"[^a-z0-9-]", "", args.new_domain.lower())
    new_service = re.sub(r"[^a-z0-9-]", "", args.new_service.lower())
    feature = args.feature
    old_domain = args.old_domain
    old_service = args.old_service
    initiatives_root = Path(args.initiatives_root)

    errors: list[str] = []
    warnings: list[str] = []

    # 1. Check source exists
    old_path = initiatives_root / old_domain / old_service
    if not old_path.exists():
        errors.append(f"Source path does not exist: {old_path}")

    # 2. Check target conflict
    new_path = initiatives_root / new_domain / new_service
    target_config = new_path / f"{feature}.yaml"
    if target_config.exists():
        errors.append(f"Feature '{feature}' already exists at {new_domain}/{new_service}")

    # 3. Check uncommitted changes
    result = subprocess.run(
        ["git", "diff", "--quiet"], capture_output=True
    )
    if result.returncode != 0:
        warnings.append("Uncommitted changes detected - commit or stash before moving")

    # 4. Check feature config exists
    source_config = old_path / f"{feature}.yaml"
    if not source_config.exists():
        errors.append(f"Feature config not found: {source_config}")

    # 5. Same location check
    if old_domain == new_domain and old_service == new_service:
        errors.append(f"Source and target are the same ({old_domain}/{old_service})")

    safe = len(errors) == 0
    files_to_move: list[str] = []

    if source_config.exists():
        files_to_move.append(f"{old_path}/{feature}.yaml -> {new_path}/{feature}.yaml")
    feature_dir = old_path / feature
    if feature_dir.is_dir():
        files_to_move.append(f"{feature_dir}/ -> {new_path}/{feature}/")

    if args.json:
        print(json.dumps({
            "safe": safe,
            "feature": feature,
            "from": f"{old_domain}/{old_service}",
            "to": f"{new_domain}/{new_service}",
            "errors": errors,
            "warnings": warnings,
            "files": files_to_move,
        }, indent=2))
    else:
        if safe:
            print("Move is safe")
        else:
            print("Move is blocked")
        print(f"  Feature: {feature}")
        print(f"  From:    {old_domain}/{old_service}")
        print(f"  To:      {new_domain}/{new_service}")
        if errors:
            print("  Errors:")
            for err in errors:
                print(f"    {err}")
        if warnings:
            print("  Warnings:")
            for warn in warnings:
                print(f"    {warn}")
        print(f"  Files: {len(files_to_move)} to relocate")

    return 0 if safe else 1


if __name__ == "__main__":
    sys.exit(main())
