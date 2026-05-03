#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
bug-reporter-ops.py — Bug intake artifact creation for the lens-bugbash suite.

Commands:
  create-bug  --title STR --description STR --chat-log STR --governance-repo PATH

Exit codes:
  0 = success (created or duplicate)
  1 = validation failure
  2 = scope violation
  3 = write error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing shared utilities from same scripts/ directory
sys.path.insert(0, str(Path(__file__).parent))

from bugbash_scope_guard import (
    ScopeViolationError,
    assert_governance_repo_exists,
    assert_path_in_scope,
)
from bugbash_schema import SchemaValidationError, validate_intake_fields


def _title_to_slug_base(title: str) -> str:
    """Convert title to a lowercase, hyphenated slug base."""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:60]  # cap at 60 chars to keep filenames sane


def _content_hash(title: str, description: str) -> str:
    """Return 8-char hex hash of (title + description) for stable content-based key."""
    raw = (title + description).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:8]


def _make_slug(title: str, description: str) -> str:
    """Generate the canonical bug slug: {title-slug}-{content-hash}."""
    base = _title_to_slug_base(title)
    content_hash = _content_hash(title, description)
    return f"{base}-{content_hash}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _frontmatter_block(
    title: str,
    description: str,
    slug: str,
    created_at: str,
) -> str:
    return (
        "---\n"
        f"title: {json.dumps(title)}\n"
        f"description: {json.dumps(description)}\n"
        "status: New\n"
        "featureId: \"\"\n"
        f"slug: {json.dumps(slug)}\n"
        f"created_at: {created_at}\n"
        f"updated_at: {created_at}\n"
        "---\n"
    )


def cmd_create_bug(args: argparse.Namespace) -> int:
    governance_repo = Path(args.governance_repo).resolve()

    # Startup validation (A7)
    assert_governance_repo_exists(governance_repo)

    # Validate intake fields
    try:
        validate_intake_fields(args.title, args.description, args.chat_log)
    except SchemaValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    slug = _make_slug(args.title, args.description)

    # Idempotency: check all status folders
    for status_folder in ("New", "Inprogress", "Fixed"):
        candidate = governance_repo / "bugs" / status_folder / f"{slug}.md"
        if candidate.exists():
            result = {"slug": slug, "path": str(candidate), "status": "duplicate"}
            print(json.dumps(result))
            return 0

    # Scope guard
    dest_path = governance_repo / "bugs" / "New" / f"{slug}.md"
    try:
        assert_path_in_scope(dest_path, governance_repo)
    except ScopeViolationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Create parent directories if missing (A4)
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: Failed to create parent directories for {dest_path}: {exc}", file=sys.stderr)
        return 3

    now = _now_iso()
    content = _frontmatter_block(args.title, args.description, slug, now) + "\n" + args.chat_log

    try:
        dest_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Failed to write artifact to {dest_path}: {exc}", file=sys.stderr)
        return 3

    result = {"slug": slug, "path": str(dest_path), "status": "created"}
    print(json.dumps(result))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bug-reporter-ops.py",
        description="Bug intake artifact creation for the lens-bugbash suite.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-bug", help="Create a single bug artifact.")
    create.add_argument("--title", required=True, help="Bug title (non-empty string)")
    create.add_argument("--description", required=True, help="Bug description (non-empty string)")
    create.add_argument("--chat-log", required=True, help="Pasted chat log content")
    create.add_argument(
        "--governance-repo",
        required=True,
        help="Absolute path to the governance repository root",
    )

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "create-bug":
        return cmd_create_bug(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
