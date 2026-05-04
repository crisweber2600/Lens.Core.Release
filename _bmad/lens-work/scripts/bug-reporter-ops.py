#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
bug-reporter-ops.py — Bug intake artifact creation for the lens-bugbash suite.

Commands:
    create-bug            --title STR --description STR --chat-log STR --governance-repo PATH [--queue New|QuickDev]
    record-quickdev-pr    --governance-repo PATH --slug STR --pr-url URL
    migrate-quickdev-bugs --governance-repo PATH

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


BUG_STATUS_FOLDERS = ("New", "QuickDev", "Inprogress", "Fixed")
INTAKE_QUEUES = ("New", "QuickDev")
QUICKDEV_MARKER = "Bug report submitted via /lens-bug-quickdev"
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*-[0-9a-f]{8}$")


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
    """Generate the canonical bug slug: {title-slug}-{content-hash}.

    When the title contains no ASCII letters or digits (e.g. only emoji or
    punctuation), the slug base is empty; in that case a ``bug-`` prefix is
    used so the result still satisfies SLUG_PATTERN.
    """
    base = _title_to_slug_base(title)
    content_hash = _content_hash(title, description)
    if not base:
        return f"bug-{content_hash}"
    return f"{base}-{content_hash}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _frontmatter_block(
    title: str,
    description: str,
    slug: str,
    created_at: str,
    status: str = "New",
) -> str:
    return (
        "---\n"
        f"title: {json.dumps(title)}\n"
        f"description: {json.dumps(description)}\n"
        f"status: {status}\n"
        "featureId: \"\"\n"
        f"slug: {json.dumps(slug)}\n"
        f"created_at: {created_at}\n"
        f"updated_at: {created_at}\n"
        "---\n"
    )


def _validate_slug(slug: str) -> str | None:
    if not SLUG_PATTERN.match(slug):
        return "--slug must be a bug slug ending in an 8-character content hash"
    return None


def _find_bug_artifact(governance_repo: Path, slug: str) -> Path | None:
    for status_folder in BUG_STATUS_FOLDERS:
        candidate = governance_repo / "bugs" / status_folder / f"{slug}.md"
        if candidate.exists():
            return candidate
    return None


def _format_frontmatter_value(key: str, value: str) -> str:
    if key in {"created_at", "updated_at", "pr_recorded_at", "status"}:
        return value
    return json.dumps(value)


def _update_frontmatter(content: str, updates: dict[str, str]) -> str:
    if not content.startswith("---"):
        raise ValueError("Content does not start with a YAML frontmatter block")
    end = content.find("\n---", 3)
    if end == -1:
        raise ValueError("Frontmatter block is not properly closed")

    frontmatter = content[3:end].lstrip("\n")
    body = content[end + 4:]
    lines = frontmatter.splitlines()
    applied: set[str] = set()
    updated_lines: list[str] = []

    for line in lines:
        if ":" in line:
            key = line.split(":", 1)[0].strip()
            if key in updates:
                updated_lines.append(f"{key}: {_format_frontmatter_value(key, updates[key])}")
                applied.add(key)
                continue
        updated_lines.append(line)

    for key, value in updates.items():
        if key not in applied:
            updated_lines.append(f"{key}: {_format_frontmatter_value(key, value)}")

    return "---\n" + "\n".join(updated_lines) + "\n---" + body


def _replace_quickdev_pr_section(content: str, pr_url: str, recorded_at: str) -> str:
    marker = "\n## QuickDev PR\n"
    section = f"\n## QuickDev PR\n\n- PR URL: {pr_url}\n- Recorded at: {recorded_at}\n"
    start = content.find(marker)
    if start == -1:
        return content.rstrip() + "\n" + section

    next_heading = content.find("\n## ", start + len(marker))
    prefix = content[:start].rstrip()
    suffix = content[next_heading:] if next_heading != -1 else ""
    return prefix + "\n" + section + suffix


def _write_quickdev_artifact(
    source_path: Path,
    dest_path: Path,
    governance_repo: Path,
    content: str,
) -> None:
    assert_path_in_scope(source_path, governance_repo)
    assert_path_in_scope(dest_path, governance_repo)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path != source_path and dest_path.exists():
        raise OSError(f"Destination already exists: {dest_path}")
    dest_path.write_text(content, encoding="utf-8")
    if dest_path != source_path:
        source_path.unlink()


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

    queue = args.queue

    # Idempotency: check all status folders
    for status_folder in BUG_STATUS_FOLDERS:
        candidate = governance_repo / "bugs" / status_folder / f"{slug}.md"
        if candidate.exists():
            result = {"slug": slug, "path": str(candidate), "status": "duplicate"}
            print(json.dumps(result))
            return 0

    # Scope guard
    dest_path = governance_repo / "bugs" / queue / f"{slug}.md"
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
    content = _frontmatter_block(args.title, args.description, slug, now, queue) + "\n" + args.chat_log

    try:
        dest_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Failed to write artifact to {dest_path}: {exc}", file=sys.stderr)
        return 3

    result = {"slug": slug, "path": str(dest_path), "status": "created"}
    print(json.dumps(result))
    return 0


def cmd_record_quickdev_pr(args: argparse.Namespace) -> int:
    governance_repo = Path(args.governance_repo).resolve()
    assert_governance_repo_exists(governance_repo)

    slug_error = _validate_slug(args.slug)
    if slug_error:
        print(f"ERROR: {slug_error}", file=sys.stderr)
        return 1
    if not args.pr_url.strip():
        print("ERROR: --pr-url is required and must not be empty", file=sys.stderr)
        return 1

    source_path = _find_bug_artifact(governance_repo, args.slug)
    if source_path is None:
        print(f"ERROR: Bug artifact not found for slug: {args.slug}", file=sys.stderr)
        return 1
    if source_path.parent.name not in {"New", "QuickDev"}:
        print(
            f"ERROR: Bug artifact is in bugs/{source_path.parent.name}; expected New or QuickDev for quickdev PR recording.",
            file=sys.stderr,
        )
        return 1

    # Guard: artifacts in bugs/New must carry the QuickDev marker to avoid
    # accidentally corrupting normal bug records.
    if source_path.parent.name == "New":
        try:
            new_content_check = source_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: Could not read artifact {source_path}: {exc}", file=sys.stderr)
            return 1
        if QUICKDEV_MARKER not in new_content_check:
            print(
                f"ERROR: Bug artifact {source_path.name} in bugs/New was not created by "
                "/lens-bug-quickdev; cannot record a QuickDev PR for it.",
                file=sys.stderr,
            )
            return 1

    recorded_at = _now_iso()
    dest_path = governance_repo / "bugs" / "QuickDev" / source_path.name
    updates = {
        "status": "QuickDev",
        "updated_at": recorded_at,
        "pr_url": args.pr_url.strip(),
        "pr_recorded_at": recorded_at,
    }

    try:
        content = source_path.read_text(encoding="utf-8")
        updated = _update_frontmatter(content, updates)
        updated = _replace_quickdev_pr_section(updated, args.pr_url.strip(), recorded_at)
        _write_quickdev_artifact(source_path, dest_path, governance_repo, updated)
    except (OSError, ValueError, ScopeViolationError) as exc:
        print(f"ERROR: Failed to record QuickDev PR for {args.slug}: {exc}", file=sys.stderr)
        return 3

    result = {
        "slug": args.slug,
        "path": str(dest_path),
        "status": "updated",
        "pr_url": args.pr_url.strip(),
    }
    print(json.dumps(result))
    return 0


def cmd_migrate_quickdev_bugs(args: argparse.Namespace) -> int:
    governance_repo = Path(args.governance_repo).resolve()
    assert_governance_repo_exists(governance_repo)

    bugs_new = governance_repo / "bugs" / "New"
    if not bugs_new.exists():
        print(json.dumps({"moved": [], "failed": []}))
        return 0

    moved: list[str] = []
    failed: list[dict[str, str]] = []
    for source_path in sorted(bugs_new.glob("*.md")):
        try:
            content = source_path.read_text(encoding="utf-8")
        except OSError as exc:
            failed.append({"path": str(source_path), "error": str(exc)})
            continue
        if QUICKDEV_MARKER not in content:
            continue

        updated_at = _now_iso()
        dest_path = governance_repo / "bugs" / "QuickDev" / source_path.name
        try:
            updated = _update_frontmatter(content, {"status": "QuickDev", "updated_at": updated_at})
            _write_quickdev_artifact(source_path, dest_path, governance_repo, updated)
            moved.append(source_path.stem)
        except (OSError, ValueError, ScopeViolationError) as exc:
            failed.append({"path": str(source_path), "error": str(exc)})

    print(json.dumps({"moved": moved, "failed": failed}))
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
    create.add_argument(
        "--queue",
        choices=INTAKE_QUEUES,
        default="New",
        help="Bug intake queue/folder to write to. Defaults to New.",
    )

    record_pr = sub.add_parser("record-quickdev-pr", help="Record a QuickDev PR URL on a bug artifact.")
    record_pr.add_argument("--governance-repo", required=True, help="Absolute path to the governance repository root")
    record_pr.add_argument("--slug", required=True, help="Bug slug returned by create-bug")
    record_pr.add_argument("--pr-url", required=True, help="Pull request URL to record")

    migrate = sub.add_parser("migrate-quickdev-bugs", help="Move existing /lens-bug-quickdev bugs into QuickDev.")
    migrate.add_argument("--governance-repo", required=True, help="Absolute path to the governance repository root")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "create-bug":
        return cmd_create_bug(args)
    if args.command == "record-quickdev-pr":
        return cmd_record_quickdev_pr(args)
    if args.command == "migrate-quickdev-bugs":
        return cmd_migrate_quickdev_bugs(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
